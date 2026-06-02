from db_parts import (
    DatabaseCoreMixin,
    DatabaseDownloadsMixin,
    DatabaseHistoryMixin,
    DatabaseModelsMixin,
    DatabaseMaintenanceMixin,
    DatabaseTransactionsMixin,
)


class DatabaseManager(
    DatabaseCoreMixin,
    DatabaseDownloadsMixin,
    DatabaseHistoryMixin,
    DatabaseModelsMixin,
    DatabaseMaintenanceMixin,
    DatabaseTransactionsMixin,
):
    def __init__(self, db_path=None):
        self._init_db(db_path)
