"""
Pagination utilities for SalesBreachPro
"""


class SimplePagination:
    """Simple pagination object for templates"""

    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.total_count = total  # Alias for template compatibility
        self.page = page
        self.current_page = page  # Alias for template compatibility
        self.per_page = per_page
        self.pages = (total + per_page - 1) // per_page if total > 0 else 1
        self.total_pages = self.pages  # Alias for template compatibility
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if page > 1 else None
        self.next_num = page + 1 if page < self.pages else None


class MockPagination:
    """Mock pagination object for error cases"""

    def __init__(self):
        self.items = []
        self.pages = 0
        self.total_pages = 0  # Add total_pages for template compatibility
        self.total = 0
        self.total_count = 0  # Add total_count for template compatibility
        self.page = 1
        self.current_page = 1
        self.has_prev = False
        self.has_next = False
        self.prev_num = None
        self.next_num = None