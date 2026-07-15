# External Council: OpenAI and Claude inside Nero

This is an optional, local-to-Nero bridge. It does not connect the ChatGPT and
Claude websites. Instead, Nero uses your own OpenAI and Anthropic API accounts
to pass a short, visible handoff between the two services.

## What happens when you press Council

```text
Your typed task
    ↓
OpenAI creates an architecture brief
    ↓
Claude responds as the builder
    ↓
OpenAI reviews the combined result
```

Each run makes three API requests. Nero sends only the task you typed and the
previous council response needed for the next handoff. It does **not** send your
saved memories, normal chat history, local files, voice data, or API keys.

## One-time setup

1. Create an API key in your OpenAI account and another in your Anthropic
   account. API usage is billed separately from ChatGPT Plus and Claude Pro.
2. Open `D:\mbd AI\config.yaml`. This private file is already ignored by Git.
3. Add this block at the end, then enter your real keys and model IDs. Use model
   IDs available to your own accounts; availability changes over time.

   ```yaml
   collaboration:
     enabled: true
     openai:
       api_key: "paste-your-OpenAI-key-here"
       model: "your-OpenAI-model-id"
     anthropic:
       api_key: "paste-your-Anthropic-key-here"
       model: "your-Claude-model-id"
   ```

4. Restart Nero with `start.bat` (or stop and start the current Nero window).
5. Type a task in Nero, then press **Council** next to the send button.
6. Read the confirmation. It tells you exactly what will leave Nero. The results
   include a **What Nero sent outside** section so you can inspect every handoff.

## Keeping control

- Leave `enabled: false` or remove the whole block whenever you do not want
  cloud escalation available.
- Never paste an API key into the chat box or share it with a person.
- Council results are suggestions. They cannot edit your files or run commands.
- To reduce cost, call Council for difficult tasks; normal Nero chat stays local.

