
class DatabaseTransactionsMixin:
    def begin_transaction(self):
        """Begin a database transaction"""
        try:
            with self._lock:
                self.conn.execute('BEGIN IMMEDIATE')
                return True
        except Exception as e:
            print(f"Error beginning transaction: {e}")
            return False

    def commit_transaction(self):
        """Commit the current transaction"""
        try:
            with self._lock:
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error committing transaction: {e}")
            return False

    def rollback_transaction(self):
        """Rollback the current transaction"""
        try:
            with self._lock:
                self.conn.rollback()
                return True
        except Exception as e:
            print(f"Error rolling back transaction: {e}")
            return False
