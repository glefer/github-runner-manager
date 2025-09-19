"""Logger classes for Docker build operations."""


class DockerBuildLogger:
    """Provides logging functionality for Docker build operations."""

    @staticmethod
    def default_logger(line: str) -> None:
        """Default logger that prints all lines."""
        print(line)

    @staticmethod
    def quiet_logger(line: str) -> None:
        """Filtered logger that only prints important build lines.

        Prints only:
        - Step indications (lines starting with "Step ")
        - Error messages (containing "error" or "failed")
        - Success messages (containing "successfully" or "success")
        """
        # Strip whitespace from the line and return early if empty
        stripped_line = line.strip()
        if not stripped_line:
            return

        # Keep Step lines
        if stripped_line.startswith("Step "):
            print(stripped_line)
            return

        # Keep lines with error or failure messages
        if any(keyword in stripped_line.lower() for keyword in ["error", "failed"]):
            print(stripped_line)
            return

        # Keep success messages
        success_keywords = [
            "success",
            "successfully",
            "successfully built",
            "successfully tagged",
        ]
        if any(keyword in stripped_line.lower() for keyword in success_keywords):
            print(stripped_line)
            return

    @classmethod
    def get_logger(cls, quiet: bool = False) -> callable:
        """Factory method to get the appropriate logger based on quiet mode."""
        return cls.quiet_logger if quiet else cls.default_logger
