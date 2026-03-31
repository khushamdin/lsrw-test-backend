import azure.cognitiveservices.speech as speechsdk
import json
import os
import subprocess
from dotenv import load_dotenv

# Load from .env if present
load_dotenv()

# Securely retrieve credentials from environment
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")


def convert_audio_to_wav(input_path: str) -> str:
    """Normalize audio to PCM 16kHz Mono WAV to avoid SPXERR_INVALID_HEADER."""
    output_path = input_path + "_converted.wav"
    try:
        # -y: overwrite, -i: input, -ar: set audio rate to 16000, -ac: set audio channels to 1
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
            check=True,
            capture_output=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"[Azure Service] Audio conversion failed: {e.stderr.decode()}")
        return input_path  # Fallback to original if conversion fails


def analyze_pronunciation(audio_path: str, reference_text: str = ""):
    """
    Performs Pronunciation Assessment using Azure Speech SDK.
    Converts audio to a compatible WAV format first to prevent SPXERR_INVALID_HEADER.
    """
    
    # 1. Normalize audio format
    normalized_path = convert_audio_to_wav(audio_path)
    
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY,
            region=SPEECH_REGION
        )

        audio_config = speechsdk.audio.AudioConfig(filename=normalized_path)

        # 2. Configure Pronunciation Assessment
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True
        )

        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        # Apply pronunciation assessment config
        pronunciation_config.apply_to(speech_recognizer)

        result = speech_recognizer.recognize_once()

        # 3. CRITICAL: On Windows, we MUST release the objects to free the file handle
        # before we can delete the normalized_path file.
        del speech_recognizer
        del audio_config
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            data = json.loads(result.json)
        elif result.reason == speechsdk.ResultReason.NoMatch:
            data = {"error": "No speech recognized"}
        else:
            data = {"error": str(result.reason)}

        # 4. Clean up temporary converted file
        if normalized_path != audio_path and os.path.exists(normalized_path):
            try:
                os.remove(normalized_path)
            except PermissionError:
                print(f"[Azure Service] Warning: Could not delete {normalized_path}, file in use.")

        return data
            
    except Exception as e:
        # Emergency cleanup try-block
        if normalized_path != audio_path and os.path.exists(normalized_path):
            try:
                os.remove(normalized_path)
            except:
                pass
        raise e


def parse_result(result_json: dict):
    """Extraction of scores from Azure Pronunciation Assessment JSON."""
    if not result_json or "error" in result_json:
        return {
            "spoken": "",
            "accuracy": 0,
            "fluency": 0,
            "completeness": 0,
            "pronunciation": 0,
            "error": result_json.get("error", "Azure API Error") if result_json else "Empty result"
        }

    # Azure returns various scores in 'NBest' -> 'PronunciationAssessment'
    try:
        best = result_json.get("NBest", [{}])[0]
        pron_result = best.get("PronunciationAssessment", {})

        return {
            "spoken": best.get("Display", best.get("Lexical", "")),
            "accuracy": pron_result.get("AccuracyScore", 0),
            "fluency": pron_result.get("FluencyScore", 0),
            "completeness": pron_result.get("CompletenessScore", 0),
            "pronunciation": pron_result.get("PronScore", 0)
        }
    except Exception:
        return {
            "spoken": "",
            "accuracy": 0, "fluency": 0, "completeness": 0, "pronunciation": 0,
            "error": "Failed to parse result"
        }