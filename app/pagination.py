from typing import List, Sequence, Tuple


def paginate(items: Sequence, offset: int, limit: int) -> Tuple[List, int]:
    if offset < 0 or limit < 1:
        raise ValueError("offset must be >= 0 and limit >= 1")
    total = len(items)
    end = offset + limit
    return list(items[offset:end]), total


def page_count(total: int, limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return -(-total // limit)