class WidgetCatalogError(Exception):
    """Base exception for all widget catalog errors."""
    pass


class WidgetNotFoundError(WidgetCatalogError):
    """Raised when a requested widget ID does not exist in the catalog."""
    def __init__(self, widget_id: str):
        self.widget_id = widget_id
        super().__init__(f"Widget with ID '{widget_id}' was not found.")


class WidgetArchivedError(WidgetCatalogError):
    """Raised when an operation requires an ACTIVE widget, but it is ARCHIVED."""
    def __init__(self, widget_id: str):
        self.widget_id = widget_id
        super().__init__(f"Widget '{widget_id}' is archived and cannot be modified or purchased.")


class WidgetDuplicateError(WidgetCatalogError):
    """Raised when trying to create a widget with an existing ID or appdev_key."""
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(f"Widget with {field} '{value}' already exists.")


class FieldImmutableError(WidgetCatalogError):
    """Raised when an update payload attempts to modify immutable fields like 'id' or 'appdev_key'."""
    def __init__(self, field_name: str):
        self.field_name = field_name
        super().__init__(f"Field '{field_name}' is immutable and cannot be updated.")


class VersionConflictError(WidgetCatalogError):
    """Raised when optimistic concurrency fails (expected_version != database_version)."""
    def __init__(self, current_version: int, expected_version: int):
        self.current_version = current_version
        self.expected_version = expected_version
        super().__init__(
            f"Version conflict: expected version {expected_version}, "
            f"but current database version is {current_version}."
        )