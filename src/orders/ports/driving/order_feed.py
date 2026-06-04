# The SSE feed's public subscription contract: the channel name the feed
# controller subscribes to and the feed listener publishes to. Lives in
# ports/driving (not in the driven listener) so the driving controller can
# reference it without importing across the driving/driven boundary.
ORDERS_CHANNEL = "orders"
