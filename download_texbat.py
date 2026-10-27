"""Compatibility entry point for the audited public real-data downloader."""
from download_real_data import download_all


def download_texbat():
    print("Downloading/verifying processed TEXBAT and the Zurich flight subset.")
    print("Raw TEXBAT BIN and account-protected IEEE files are excluded.")
    return download_all()


if __name__ == '__main__':
    download_texbat()
