from typing import Any, Optional


class ListUtil:
    """Utility class for list operations."""
    
    @staticmethod
    def get_first_item(items: Any) -> Optional[Any]:
        """Safely get the first item from a list.
        
        Args:
            items: List or any other type
            
        Returns:
            First item if items is a non-empty list, None otherwise
        """
        if isinstance(items, list) and len(items) > 0:
            return items[0]
        return None

