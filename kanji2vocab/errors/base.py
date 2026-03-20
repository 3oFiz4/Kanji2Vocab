class AppError(Exception):
    def __init__(self, message: str, solution: str | None = None):
        super().__init__(message)
        self.solution = solution