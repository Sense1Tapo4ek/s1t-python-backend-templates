class JoinPolicy:
    @staticmethod
    def is_complete(*, done_count: int, fan_out: int) -> bool:
        return done_count >= fan_out
