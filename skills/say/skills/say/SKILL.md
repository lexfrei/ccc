---
name: say
description: Speak text aloud using macOS TTS with automatic voice selection.
argument-hint: "[text to speak]"
disable-model-invocation: true
allowed-tools: Bash
---

Speak text aloud using macOS `say` command. Voice is selected automatically by the system based on the text language.

## Arguments

Parse `<args>` as the text to speak. If no arguments provided, speak a summary of what you just did.

## Execution

```bash
say "<text>"
```

macOS auto-detects the language and picks the best installed voice.

## Notes

- Keep phrases short and clear
- For status updates, summarize in one sentence
- No need to specify voice — macOS selects the appropriate one from installed voices
