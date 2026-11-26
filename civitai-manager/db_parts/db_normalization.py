import json
import unicodedata


def normalize_key(value):
    if value is None:
        return None
    value = unicodedata.normalize("NFC", str(value).strip())
    return value.casefold() if value else None


def normalize_tags(value):
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for item in value:
        name = item.get("name") if isinstance(item, dict) else item
        if not isinstance(name, str):
            continue
        name = name.strip()
        key = normalize_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        result.append((name, key))
    return result


def normalize_creator(value):
    if isinstance(value, dict):
        username = value.get("username")
        image_url = value.get("image") or value.get("imageUrl")
    else:
        username = value
        image_url = None
    if not isinstance(username, str) or not username.strip():
        return None, None
    return username.strip(), image_url.strip() if isinstance(image_url, str) and image_url.strip() else None


def merge_raw_json(existing, incoming):
    existing_obj = existing if isinstance(existing, dict) else {}
    incoming_obj = incoming if isinstance(incoming, dict) else {}
    merged = dict(existing_obj)
    for key, value in incoming_obj.items():
        if isinstance(value, list):
            merged[key] = list(value)
        elif value is not None:
            merged[key] = value
    return merged


def parse_json_object(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def select_main_tag(tags, priority=None):
    normalized = normalize_tags(tags)
    if not normalized:
        return "Other"
    priority_names = []
    if isinstance(priority, str):
        priority_names = [p.strip() for p in priority.split(",") if p.strip()]
    elif isinstance(priority, (list, tuple)):
        priority_names = [str(p).strip() for p in priority if str(p).strip()]
    by_key = {key: name for name, key in normalized}
    for priority_name in priority_names:
        key = normalize_key(priority_name)
        if key in by_key:
            return by_key[key]
    return normalized[0][0]


def upsert_creator(cursor, creator_value):
    username, image_url = normalize_creator(creator_value)
    if username is None:
        return None
    key = normalize_key(username)
    cursor.execute("SELECT creator_id, image_url FROM creators WHERE username_key=?", (key,))
    row = cursor.fetchone()
    if row:
        creator_id, existing_url = row
        if image_url:
            cursor.execute("UPDATE creators SET image_url=? WHERE creator_id=?", (image_url, creator_id))
        return creator_id
    cursor.execute(
        "INSERT INTO creators (username, username_key, image_url) VALUES (?, ?, ?)",
        (username, key, image_url),
    )
    return cursor.lastrowid


def upsert_model(cursor, model_data, existing_raw=None):
    model_id = model_data.get("id")
    if not model_id:
        return False
    existing = parse_json_object(existing_raw)
    raw = merge_raw_json(existing, model_data)
    creator_id = upsert_creator(cursor, model_data.get("creator"))

    cursor.execute("PRAGMA table_info(models)")
    model_columns = {row[1] for row in cursor.fetchall()}
    if "raw_json" in model_columns:
        cursor.execute("SELECT raw_json FROM models WHERE model_id=?", (model_id,))
    elif "metadata" in model_columns:
        cursor.execute("SELECT metadata FROM models WHERE model_id=?", (model_id,))
    else:
        cursor.execute("SELECT NULL")
    row = cursor.fetchone()
    if row:
        raw = merge_raw_json(parse_json_object(row[0]), model_data)

    cursor.execute(
        """
        INSERT INTO models (
            model_id, creator_id, name, type, base_model, url, description,
            published_at, updated_at, nsfw_level, availability,
            allow_no_credit, allow_derivatives, allow_different_license,
            download_count, thumbs_up_count, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(model_id) DO UPDATE SET
            creator_id=CASE
                WHEN excluded.creator_id IS NULL THEN models.creator_id
                ELSE excluded.creator_id
            END,
            name=CASE WHEN excluded.name IS NULL THEN models.name ELSE excluded.name END,
            type=CASE WHEN excluded.type IS NULL THEN models.type ELSE excluded.type END,
            base_model=CASE WHEN excluded.base_model IS NULL THEN models.base_model ELSE excluded.base_model END,
            url=CASE WHEN excluded.url IS NULL THEN models.url ELSE excluded.url END,
            description=CASE WHEN excluded.description IS NULL THEN models.description ELSE excluded.description END,
            published_at=CASE WHEN excluded.published_at IS NULL THEN models.published_at ELSE excluded.published_at END,
            updated_at=CASE WHEN excluded.updated_at IS NULL THEN models.updated_at ELSE excluded.updated_at END,
            nsfw_level=CASE WHEN excluded.nsfw_level IS NULL THEN models.nsfw_level ELSE excluded.nsfw_level END,
            availability=CASE WHEN excluded.availability IS NULL THEN models.availability ELSE excluded.availability END,
            allow_no_credit=CASE WHEN excluded.allow_no_credit IS NULL THEN models.allow_no_credit ELSE excluded.allow_no_credit END,
            allow_derivatives=CASE WHEN excluded.allow_derivatives IS NULL THEN models.allow_derivatives ELSE excluded.allow_derivatives END,
            allow_different_license=CASE WHEN excluded.allow_different_license IS NULL THEN models.allow_different_license ELSE excluded.allow_different_license END,
            download_count=CASE WHEN excluded.download_count IS NULL THEN models.download_count ELSE excluded.download_count END,
            thumbs_up_count=CASE WHEN excluded.thumbs_up_count IS NULL THEN models.thumbs_up_count ELSE excluded.thumbs_up_count END,
            raw_json=excluded.raw_json
        """,
        (
            model_id,
            creator_id,
            model_data.get("name"),
            model_data.get("type"),
            model_data.get("baseModel") or model_data.get("base_model"),
            model_data.get("url") or f"https://civitai.com/models/{model_id}",
            model_data.get("description"),
            model_data.get("publishedAt") or model_data.get("createdAt") or model_data.get("published_at"),
            model_data.get("updatedAt") or model_data.get("updated_at"),
            model_data.get("nsfwLevel") if "nsfwLevel" in model_data else model_data.get("nsfw_level"),
            model_data.get("availability"),
            model_data.get("allowNoCredit") if "allowNoCredit" in model_data else model_data.get("allow_no_credit"),
            model_data.get("allowDerivatives") if "allowDerivatives" in model_data else model_data.get("allow_derivatives"),
            model_data.get("allowDifferentLicense") if "allowDifferentLicense" in model_data else model_data.get("allow_different_license"),
            model_data.get("downloadCount") if "downloadCount" in model_data else model_data.get("download_count"),
            model_data.get("thumbsUpCount") if "thumbsUpCount" in model_data else model_data.get("thumbs_up_count"),
            json.dumps(raw, ensure_ascii=False),
        ),
    )
    if "creator" in model_data:
        if creator_id is None:
            cursor.execute("UPDATE models SET creator_id=NULL WHERE model_id=?", (model_id,))

    if "tags" in model_data:
        cursor.execute("DELETE FROM model_tags WHERE model_id=?", (model_id,))
        for position, (name, key) in enumerate(normalize_tags(model_data.get("tags"))):
            cursor.execute("INSERT OR IGNORE INTO tags (name, name_key) VALUES (?, ?)", (name, key))
            cursor.execute("SELECT tag_id FROM tags WHERE name_key=?", (key,))
            tag_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO model_tags (model_id, tag_id, position) VALUES (?, ?, ?)",
                (model_id, tag_id, position),
            )

    if "allowCommercialUse" in model_data:
        cursor.execute("DELETE FROM model_commercial_uses WHERE model_id=?", (model_id,))
        uses = model_data.get("allowCommercialUse")
        if isinstance(uses, list):
            for position, use in enumerate(uses):
                if isinstance(use, str) and use.strip():
                    cursor.execute(
                        "INSERT INTO model_commercial_uses (model_id, position, use_name) VALUES (?, ?, ?)",
                        (model_id, position, use.strip()),
                    )
    return True


def upsert_version(cursor, version_data):
    version_id = version_data.get("id")
    model_id = version_data.get("modelId") or version_data.get("model_id") or (version_data.get("model") or {}).get("id")
    if not version_id or not model_id:
        return False
    cursor.execute("PRAGMA table_info(versions)")
    version_columns = {row[1] for row in cursor.fetchall()}
    if "raw_json" in version_columns:
        cursor.execute("SELECT raw_json FROM versions WHERE version_id=?", (version_id,))
    elif "metadata" in version_columns:
        cursor.execute("SELECT metadata FROM versions WHERE version_id=?", (version_id,))
    else:
        cursor.execute("SELECT NULL")
    row = cursor.fetchone()
    existing = parse_json_object(row[0]) if row else {}
    raw = merge_raw_json(existing, version_data)
    cursor.execute(
        """
        INSERT INTO versions (
            version_id, model_id, name, base_model, base_model_type, status,
            availability, published_at, updated_at, nsfw_level, description,
            download_count, thumbs_up_count, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(version_id) DO UPDATE SET
            model_id=CASE WHEN excluded.model_id IS NULL THEN versions.model_id ELSE excluded.model_id END,
            name=CASE WHEN excluded.name IS NULL THEN versions.name ELSE excluded.name END,
            base_model=CASE WHEN excluded.base_model IS NULL THEN versions.base_model ELSE excluded.base_model END,
            base_model_type=CASE WHEN excluded.base_model_type IS NULL THEN versions.base_model_type ELSE excluded.base_model_type END,
            status=CASE WHEN excluded.status IS NULL THEN versions.status ELSE excluded.status END,
            availability=CASE WHEN excluded.availability IS NULL THEN versions.availability ELSE excluded.availability END,
            published_at=CASE WHEN excluded.published_at IS NULL THEN versions.published_at ELSE excluded.published_at END,
            updated_at=CASE WHEN excluded.updated_at IS NULL THEN versions.updated_at ELSE excluded.updated_at END,
            nsfw_level=CASE WHEN excluded.nsfw_level IS NULL THEN versions.nsfw_level ELSE excluded.nsfw_level END,
            description=CASE WHEN excluded.description IS NULL THEN versions.description ELSE excluded.description END,
            download_count=CASE WHEN excluded.download_count IS NULL THEN versions.download_count ELSE excluded.download_count END,
            thumbs_up_count=CASE WHEN excluded.thumbs_up_count IS NULL THEN versions.thumbs_up_count ELSE excluded.thumbs_up_count END,
            raw_json=excluded.raw_json
        """,
        (
            version_id,
            model_id,
            version_data.get("name"),
            version_data.get("baseModel") or version_data.get("base_model"),
            version_data.get("baseModelType") or version_data.get("base_model_type"),
            version_data.get("status"),
            version_data.get("availability"),
            version_data.get("publishedAt") or version_data.get("createdAt") or version_data.get("published_at"),
            version_data.get("updatedAt") or version_data.get("updated_at"),
            version_data.get("nsfwLevel") if "nsfwLevel" in version_data else version_data.get("nsfw_level"),
            version_data.get("description"),
            version_data.get("downloadCount") if "downloadCount" in version_data else version_data.get("download_count"),
            version_data.get("thumbsUpCount") if "thumbsUpCount" in version_data else version_data.get("thumbs_up_count"),
            json.dumps(raw, ensure_ascii=False),
        ),
    )
    if "trainedWords" in version_data:
        cursor.execute("DELETE FROM version_trained_words WHERE version_id=?", (version_id,))
        words = version_data.get("trainedWords")
        if isinstance(words, list):
            for position, word in enumerate(words):
                if isinstance(word, str):
                    cursor.execute(
                        "INSERT INTO version_trained_words (version_id, position, word) VALUES (?, ?, ?)",
                        (version_id, position, word),
                    )
    return True


def upsert_files(cursor, version_id, file_entries, path_hint=None):
    if not isinstance(file_entries, list):
        return
    for file_entry in file_entries:
        if not isinstance(file_entry, dict):
            continue
        api_file_id = file_entry.get("id")
        hashes = file_entry.get("hashes") if isinstance(file_entry.get("hashes"), dict) else {}
        sha256 = hashes.get("SHA256") or file_entry.get("sha256")
        size_kb = file_entry.get("sizeKB")
        if size_kb is None:
            size_kb = file_entry.get("size_kb")
        existing_file_id = None
        if api_file_id is not None:
            row = cursor.execute(
                "SELECT id FROM files WHERE api_file_id=?",
                (api_file_id,),
            ).fetchone()
            existing_file_id = row[0] if row else None
        if existing_file_id is None and sha256:
            row = cursor.execute(
                "SELECT id FROM files WHERE version_id=? AND UPPER(COALESCE(sha256,''))=UPPER(?)",
                (version_id, sha256),
            ).fetchone()
            existing_file_id = row[0] if row else None
        if existing_file_id is None and file_entry.get("name"):
            row = cursor.execute(
                "SELECT id FROM files WHERE version_id=? AND name=?",
                (version_id, file_entry.get("name")),
            ).fetchone()
            existing_file_id = row[0] if row else None
        if existing_file_id is not None:
            cursor.execute(
                """
                UPDATE files SET
                    api_file_id=COALESCE(?, api_file_id),
                    version_id=?,
                    name=COALESCE(?, name),
                    type=COALESCE(?, type),
                    size_kb=COALESCE(?, size_kb),
                    format=COALESCE(?, format),
                    download_url=COALESCE(?, download_url),
                    is_primary=COALESCE(?, is_primary),
                    sha256=COALESCE(?, sha256),
                    path=COALESCE(?, path),
                    pickle_scan=COALESCE(?, pickle_scan),
                    virus_scan=COALESCE(?, virus_scan),
                    scanned_at=COALESCE(?, scanned_at)
                WHERE id=?
                """,
                (
                    api_file_id,
                    version_id,
                    file_entry.get("name"),
                    file_entry.get("type"),
                    size_kb,
                    file_entry.get("format"),
                    file_entry.get("downloadUrl") or file_entry.get("download_url"),
                    1 if file_entry.get("primary") or file_entry.get("isPrimary") or file_entry.get("is_primary") else None,
                    sha256,
                    path_hint,
                    file_entry.get("pickleScan") or file_entry.get("pickle_scan"),
                    file_entry.get("virusScan") or file_entry.get("virus_scan"),
                    file_entry.get("scannedAt") or file_entry.get("scanned_at"),
                    existing_file_id,
                ),
            )
            continue
        cursor.execute(
            """
            INSERT INTO files (
                api_file_id, version_id, name, type, size_kb, format,
                download_url, is_primary, sha256, path,
                pickle_scan, virus_scan, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(api_file_id) DO UPDATE SET
                version_id=excluded.version_id,
                name=CASE WHEN excluded.name IS NULL THEN files.name ELSE excluded.name END,
                type=CASE WHEN excluded.type IS NULL THEN files.type ELSE excluded.type END,
                size_kb=CASE WHEN excluded.size_kb IS NULL THEN files.size_kb ELSE excluded.size_kb END,
                format=CASE WHEN excluded.format IS NULL THEN files.format ELSE excluded.format END,
                download_url=CASE WHEN excluded.download_url IS NULL THEN files.download_url ELSE excluded.download_url END,
                is_primary=CASE WHEN excluded.is_primary IS NULL THEN files.is_primary ELSE excluded.is_primary END,
                sha256=CASE WHEN excluded.sha256 IS NULL THEN files.sha256 ELSE excluded.sha256 END,
                path=CASE WHEN excluded.path IS NULL THEN files.path ELSE excluded.path END,
                pickle_scan=CASE WHEN excluded.pickle_scan IS NULL THEN files.pickle_scan ELSE excluded.pickle_scan END,
                virus_scan=CASE WHEN excluded.virus_scan IS NULL THEN files.virus_scan ELSE excluded.virus_scan END,
                scanned_at=CASE WHEN excluded.scanned_at IS NULL THEN files.scanned_at ELSE excluded.scanned_at END
            """,
            (
                api_file_id,
                version_id,
                file_entry.get("name"),
                file_entry.get("type"),
                size_kb,
                file_entry.get("format"),
                file_entry.get("downloadUrl") or file_entry.get("download_url"),
                1 if file_entry.get("primary") or file_entry.get("isPrimary") or file_entry.get("is_primary") else 0,
                sha256,
                path_hint,
                file_entry.get("pickleScan") or file_entry.get("pickle_scan"),
                file_entry.get("virusScan") or file_entry.get("virus_scan"),
                file_entry.get("scannedAt") or file_entry.get("scanned_at"),
            ),
        )
