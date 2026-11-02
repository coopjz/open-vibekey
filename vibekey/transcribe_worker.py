"""Cancellable subprocess boundary for transcription, including HTTP requests."""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def transcribe(audio, config):
    backend = config["backend"]
    timeout = config["timeout_seconds"]
    if backend == "command":
        argv = [arg.replace("{audio}", audio).replace("{language}", config["language"])
                for arg in config["command"]]
        if not argv:
            raise ValueError("Configure an executable and {audio} argument first")
        if not any("{audio}" in arg for arg in config["command"]):
            argv.append(audio)
        # Output is bounded by the parent file-size monitor.
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, timeout=timeout)
        if result.returncode:
            raise RuntimeError("Transcription command failed")
        return None  # external command already wrote UTF-8 to stdout
    if backend == "whisper":
        model = config["model_path"]
        if not Path(model).is_file():
            raise ValueError("Whisper model does not exist")
        output = str(Path(audio).with_suffix(".transcript"))
        argv = [config["whisper_executable"], "-m", model, "-f", audio,
                "-l", config["language"], "-otxt", "-of", output, "-nt", "-np"]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=timeout)
        if result.returncode:
            raise RuntimeError("whisper.cpp failed")
        return Path(output + ".txt").read_text(encoding="utf-8").strip()
    if backend == "api":
        url = config["api_url"]
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
        ):
            raise ValueError("Remote transcription requires HTTPS")
        if parsed.username or parsed.password:
            raise ValueError("Credentials must be an environment variable")
        token = os.environ.get(config["api_key_env"], "")
        if not token:
            raise ValueError("Transcription API credential is missing")
        boundary = "vibekey-" + uuid.uuid4().hex
        parts = []
        fields = {"model": config["api_model"], "response_format": "json"}
        if config["language"] != "auto":
            fields["language"] = config["language"]
        for name, value in fields.items():
            parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                          % (boundary, name, value)).encode("utf-8"))
        parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
                      'Content-Type: audio/wav\r\n\r\n' % boundary).encode("ascii"))
        parts.extend([Path(audio).read_bytes(), ("\r\n--%s--\r\n" % boundary).encode("ascii")])
        request = urllib.request.Request(url, data=b"".join(parts), headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        })

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None  # Never forward an Authorization header to redirects.
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            body = response.read(1048577)
        if len(body) > 1048576:
            raise ValueError("Transcription response too large")
        text = json.loads(body.decode("utf-8")).get("text")
        if not isinstance(text, str):
            raise ValueError("Transcription response missing text")
        return text.strip()
    raise ValueError("Unknown backend")


def main():
    try:
        config = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        text = transcribe(sys.argv[1], config)
        if text is not None:
            sys.stdout.buffer.write(text.encode("utf-8"))
    except Exception:
        # Parent reports a generic error. No API response bodies or tokens.
        sys.exit(1)


if __name__ == "__main__":
    main()
