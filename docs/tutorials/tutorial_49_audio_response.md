# Tutorial 49: Voice output — turn an agent's reply into speech

A real agent often needs to *talk*, not just type. This tutorial pairs
locus's regular chat-completions agent (text in, text out) with OCI's
hosted text-to-speech model so the response can be spoken aloud.

Pipeline::

    user prompt ──▶ Agent (OCIOpenAIModel · openai.gpt-5.5)
                       │
                       │  reply text
                       ▼
                 OCI /openai/v1/audio/speech
                 (openai.gpt-4o-mini-tts)
                       │
                       │  mp3 bytes
                       ▼
                 ./tutorial_49_response.mp3

Why this is differentiated:

* Same OCI v1 transport as the rest of the tutorials — one signer,
  one base URL, one set of credentials. No separate audio service to
  configure.
* Bring-your-own-voice via the ``voice=`` parameter (alloy, ash, ballad,
  coral, echo, sage, shimmer, verse).
* Output is a normal MP3 file you can pipe straight into a frontend
  ``<audio>`` element, an IVR system, or a podcast feed.

Run::

    LOCUS_MODEL_PROVIDER=oci \
    LOCUS_OCI_PROFILE=MY_PROFILE \
    LOCUS_OCI_REGION=us-chicago-1 \
    LOCUS_OCI_AUTH_TYPE=security_token \
    LOCUS_OCI_COMPARTMENT=ocid1.compartment.oc1..…  \
    python examples/tutorial_49_audio_response.py

    # then
    afplay tutorial_49_response.mp3   # macOS
    # or open it in any media player

Difficulty: Intermediate
Prerequisites: tutorial_01 (basic agent), tutorial_38 (multimodal)

## Source

```python
--8<-- "examples/tutorial_49_audio_response.py"
```
