class ErrorHandler:
    def __init__(self, logger):
        self.logger = logger

    def handle(self, err: Exception):
        if hasattr(err, "solution"):
            self.logger.log(str(err), "e")
            if err.solution:
                self.logger.log(f"Fix: {err.solution}", "i")
        else:
            self.logger.log(f"Unexpected: {err}", "e")