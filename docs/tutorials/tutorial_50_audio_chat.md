# Tutorial 50: Voice in → voice out chat via OCI gpt-audio

Tutorial 49 was *text in, voice out* (Agent + dedicated TTS). This is
the next step: a single multimodal call to ``openai.gpt-audio`` that
takes an audio file as the user message and replies with both text
and audio in one shot.

Pipeline::

                         (synth via tutorial 49 if absent)
                                       │
                                       ▼
                          ./tutorial_50_question.wav
                                       │
                                       ▼
              POST /openai/v1/chat/completions
              model=openai.gpt-audio
              modalities=["text","audio"]
              messages[0].content = [{type:"input_audio", ...}]
                                       │
                                       │ {choices[0].message.audio.data, .transcript}
                                       ▼
                          ./tutorial_50_answer.mp3
                          (+ printed transcript)

Why this is differentiated:

* One model call replaces three (transcribe → chat → synthesize),
  cutting latency for voice agents.
* Same OCI v1 signer + base URL the rest of the tutorials use — no
  realtime websocket plumbing required.
* ``gpt-audio`` returns a PCM-16 audio block, which the SDK lets you
  re-encode to mp3 for storage / streaming.

Run::

    LOCUS_MODEL_PROVIDER=oci \
    LOCUS_OCI_PROFILE=MY_PROFILE \
    LOCUS_OCI_REGION=us-chicago-1 \
    LOCUS_OCI_AUTH_TYPE=security_token \
    LOCUS_OCI_COMPARTMENT=ocid1.compartment.oc1..…  \
    python examples/tutorial_50_audio_chat.py

    afplay tutorial_50_answer.mp3   # macOS

Difficulty: Advanced
Prerequisites: tutorial_49_audio_response (TTS pipeline)

## Source

```python
--8<-- "examples/tutorial_50_audio_chat.py"
```
