import whisper

model = whisper.load_model("base")

def transcribe_audio(audio_file_path: str) -> str:
    result = model.transcribe(audio_file_path)
    return result["text"]
