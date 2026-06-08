from enum import StrEnum


class JobKind(StrEnum):
    TRANSCODE = "transcode"
    PLAGIARISM = "plagiarism"
    STT = "stt"
