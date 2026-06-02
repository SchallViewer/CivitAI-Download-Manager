import logging


class DiagnosticsMixin:
    def _ensure_logger(self):
        logger = getattr(self, 'logger', None)
        if logger is not None:
            return logger

        logger = logging.getLogger('civitai_manager')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        self.logger = logger
        return logger

    def _log_debug(self, message):
        try:
            self._ensure_logger().debug(message)
        except Exception:
            print(message)

    def _log_warning(self, message):
        try:
            self._ensure_logger().warning(message)
        except Exception:
            print(message)

    def _log_exception(self, context, exc):
        try:
            self._ensure_logger().warning('%s: %s', context, exc)
        except Exception:
            print(f'{context}: {exc}')
