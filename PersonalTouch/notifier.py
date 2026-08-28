import os
import platform
import uuid

NOTIFY_SOUND = r"C:\Windows\Media\notify.wav"


def beep():
    """
    Play a notification sound.

    Cmder/ConEmu injects hooks that swallow winsound.PlaySound and
    winsound.Beep, which is why the alert works in PyCharm but not in
    Cmder. MCI wave playback is not hooked, so it works in both.
    """
    if platform.system() == "Windows":
        if os.path.isfile(NOTIFY_SOUND) and _play_wav_mci(NOTIFY_SOUND):
            return
        if _play_wav_winsound(NOTIFY_SOUND):
            return

    print("\a", end="", flush=True)


def _play_wav_mci(path):
    try:
        import ctypes

        mci_send_string = ctypes.windll.winmm.mciSendStringW
        mci_send_string.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        mci_send_string.restype = ctypes.c_uint

        alias = f"oscabeep{uuid.uuid4().hex[:8]}"
        buffer = ctypes.create_unicode_buffer(255)

        def send(command):
            return mci_send_string(command, buffer, 254, None)

        error = send(f'open "{path}" type waveaudio alias {alias}')
        if error:
            return False

        try:
            return send(f"play {alias} wait") == 0
        finally:
            send(f"close {alias}")
    except Exception:
        return False


def _play_wav_winsound(path):
    try:
        import winsound

        if not os.path.isfile(path):
            return False

        winsound.PlaySound(
            path,
            winsound.SND_FILENAME | winsound.SND_NODEFAULT,
        )
        return True
    except Exception:
        return False


if __name__ == "__main__":
    beep()
