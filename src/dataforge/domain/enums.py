"""Status and method values shared with the Postgres enum types."""

from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "Pending"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"
    RETURNED = "Returned"


class PaymentStatus(StrEnum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    CONFIRMED = "Confirmed"
    FAILED = "Failed"


class PaymentMethod(StrEnum):
    CASH = "Cash"
    CARD = "Card"
    TRANSFER = "Transfer"
