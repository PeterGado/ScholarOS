# Day 20

The more I think about AI in research and writing, the more I come back to this:

Generating text is not the same as helping someone make progress.

In production, a chat reply or document-processing task doesn’t run to completion inside the user’s HTTP request. The API records a Work Item in PostgreSQL; background worker threads claim queued work, execute it, and persist whether it succeeded or failed.

That’s an asynchronous processing pattern. It keeps slower operations—especially calls to an external AI provider—off the immediate request path and gives the application a concrete status to report.

But a background queue is plumbing, not product value by itself. The useful question is whether the work it enables helps someone understand their sources or make a better next step, rather than simply generating more text.

What makes an AI tool genuinely useful in your day-to-day work? Can you think of a time it saved effort—or created more?

#AI #ProductBuilding #Research
