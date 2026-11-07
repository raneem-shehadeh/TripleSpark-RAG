# Triple Spark AI

Build a modern, professional and responsive AI chatbot web application called Triple Spark.

Requirements:

React with TypeScript.

Clean, premium UI with a purple and deep navy color palette.

Welcome screen with Triple Spark branding.

Chat interface with user and assistant message bubbles.

Support Arabic RTL and English LTR automatically.

Message input and Send button.

Display AI answers with a Sources section below each answer.

Each source displays its filename and page number.

Multiple sources per answer.

Mock responses for demonstration.

Loading indicator while waiting for responses.

Friendly no-information-found state.

API error handling.

Prevent empty messages.

Support multiple messages in one conversation.

Responsive desktop and mobile layouts.

Architecture:

Keep API calls in a separate service file such as src/services/chatApi.ts.

Use mock responses for now.

Prepare the service for future integration with POST /api/ask.

Expected request: { "question": "..." }

Expected response: { "answer": "...", "sources": [{ "source": "registration.pdf", "page": 3 }] }

Do not connect directly to Gemini.

Do not add authentication or a database.

Make the application polished and ready for a hackathon demonstration.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/04cf2617-882f-4cc5-85a9-6440f655b80d).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
