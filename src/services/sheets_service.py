"""Google Sheets service for data persistence."""

import logging
import time
from typing import Any, Optional

import gspread
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound


class SheetsService:
    """
    Google Sheets API integration service.

    Provides authentication, read/write operations, batching, and rate limiting.
    """

    # Google Sheets API scope
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    # Sheet names
    SHEET_SCHEDULE = "Schedule"
    SHEET_RECURRING_PATTERNS = "RecurringPatterns"
    SHEET_AUDIT_LOG = "AuditLog"
    SHEET_CONFIGURATION = "Configuration"

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_file: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """
        Initialize Google Sheets service.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            credentials_file: Path to service account JSON key file
            max_retries: Maximum number of retries for failed requests
            base_delay: Base delay for exponential backoff (seconds)
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logging.getLogger("discord_host_scheduler.sheets")

        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    def _authenticate(self) -> None:
        """Authenticate with Google Sheets API using service account."""
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=self.SCOPES
            )
            self._client = gspread.authorize(credentials)
            self.logger.info("Successfully authenticated with Google Sheets API")
        except (GoogleAuthError, FileNotFoundError) as e:
            self.logger.error(f"Authentication failed: {e}")
            raise

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """
        Get spreadsheet object (authenticate if needed).

        Returns:
            Spreadsheet object

        Raises:
            SpreadsheetNotFound: If spreadsheet ID is invalid
        """
        if self._spreadsheet is None:
            if self._client is None:
                self._authenticate()

            try:
                self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
                self.logger.info(f"Opened spreadsheet: {self._spreadsheet.title}")
            except SpreadsheetNotFound:
                self.logger.error(f"Spreadsheet not found: {self.spreadsheet_id}")
                raise

        return self._spreadsheet

    def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """
        Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            APIError: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except APIError as e:
                # Check if rate limited (429)
                if e.response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        # Calculate delay with exponential backoff and jitter
                        delay = self.base_delay * (2**attempt)
                        jitter = delay * 0.1  # 10% jitter
                        import random

                        delay = delay + random.uniform(-jitter, jitter)

                        self.logger.warning(
                            f"Rate limited (429), retrying in {delay:.2f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(delay)
                    else:
                        self.logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                        raise
                else:
                    # Non-rate-limit error, raise immediately
                    self.logger.error(f"API error: {e}")
                    raise

        raise APIError("Max retries exceeded")

    def get_sheet(self, sheet_name: str) -> gspread.Worksheet:
        """
        Get worksheet by name.

        Args:
            sheet_name: Name of worksheet

        Returns:
            Worksheet object

        Raises:
            gspread.exceptions.WorksheetNotFound: If worksheet doesn't exist
        """
        spreadsheet = self._get_spreadsheet()
        return spreadsheet.worksheet(sheet_name)

    def read_all_records(self, sheet_name: str) -> list[dict]:
        """
        Read all records from sheet as list of dictionaries.

        Args:
            sheet_name: Name of worksheet

        Returns:
            List of dictionaries (one per row)
        """

        def _read():
            sheet = self.get_sheet(sheet_name)
            return sheet.get_all_records()

        records = self._retry_with_backoff(_read)
        self.logger.info(f"Read {len(records)} records from sheet '{sheet_name}'")
        return records

    def read_values(self, sheet_name: str, range_name: str) -> list[list]:
        """
        Read values from specific range.

        Args:
            sheet_name: Name of worksheet
            range_name: Range in A1 notation (e.g., "A1:D10")

        Returns:
            List of lists (rows)
        """

        def _read():
            sheet = self.get_sheet(sheet_name)
            return sheet.get(range_name)

        values = self._retry_with_backoff(_read)
        self.logger.info(f"Read {len(values)} rows from range '{range_name}' in '{sheet_name}'")
        return values

    def append_row(self, sheet_name: str, row_data: list) -> None:
        """
        Append row to sheet.

        Args:
            sheet_name: Name of worksheet
            row_data: List of values for row
        """

        def _append():
            sheet = self.get_sheet(sheet_name)
            sheet.append_row(row_data)

        self._retry_with_backoff(_append)
        self.logger.info(f"Appended row to sheet '{sheet_name}'")

    def update_cell(self, sheet_name: str, row: int, col: int, value: Any) -> None:
        """
        Update single cell.

        Args:
            sheet_name: Name of worksheet
            row: Row number (1-indexed)
            col: Column number (1-indexed)
            value: Value to set
        """

        def _update():
            sheet = self.get_sheet(sheet_name)
            sheet.update_cell(row, col, value)

        self._retry_with_backoff(_update)
        self.logger.info(f"Updated cell ({row}, {col}) in sheet '{sheet_name}'")

    def update_range(self, sheet_name: str, range_name: str, values: list[list]) -> None:
        """
        Update range of cells (batch operation).

        Args:
            sheet_name: Name of worksheet
            range_name: Range in A1 notation (e.g., "A1:D10")
            values: List of lists (rows)
        """

        def _update():
            sheet = self.get_sheet(sheet_name)
            sheet.update(range_name, values)

        self._retry_with_backoff(_update)
        self.logger.info(f"Updated range '{range_name}' in sheet '{sheet_name}'")

    def batch_update(self, sheet_name: str, updates: list[dict]) -> None:
        """
        Perform batch update operations.

        Args:
            sheet_name: Name of worksheet
            updates: List of update dictionaries with 'range' and 'values' keys
        """

        def _batch_update():
            sheet = self.get_sheet(sheet_name)
            sheet.batch_update(updates)

        self._retry_with_backoff(_batch_update)
        self.logger.info(f"Batch updated {len(updates)} ranges in sheet '{sheet_name}'")

    def find_row(self, sheet_name: str, column: int, value: str) -> Optional[int]:
        """
        Find row number where column matches value.

        Args:
            sheet_name: Name of worksheet
            column: Column number to search (1-indexed)
            value: Value to find

        Returns:
            Row number (1-indexed) if found, None otherwise
        """

        def _find():
            sheet = self.get_sheet(sheet_name)
            cell = sheet.find(value, in_column=column)
            return cell.row if cell else None

        return self._retry_with_backoff(_find)

    def delete_row(self, sheet_name: str, row: int) -> None:
        """
        Delete row from sheet.

        Args:
            sheet_name: Name of worksheet
            row: Row number to delete (1-indexed)
        """

        def _delete():
            sheet = self.get_sheet(sheet_name)
            sheet.delete_rows(row)

        self._retry_with_backoff(_delete)
        self.logger.info(f"Deleted row {row} from sheet '{sheet_name}'")

    def clear_sheet(self, sheet_name: str) -> None:
        """
        Clear all data from sheet (except header row).

        Args:
            sheet_name: Name of worksheet
        """

        def _clear():
            sheet = self.get_sheet(sheet_name)
            # Clear all but keep header row
            sheet.delete_rows(2, sheet.row_count)

        self._retry_with_backoff(_clear)
        self.logger.info(f"Cleared sheet '{sheet_name}'")
