# Day 19

I don’t think a useful tool should do the thinking for you.

In ScholarOS, the AI provider sits behind a provider abstraction. The current integration uses Google’s Gemini SDK for text generation and embeddings, while the application calls shared provider interfaces rather than embedding Gemini-specific calls throughout the product.

That boundary matters because a provider is an implementation choice, not the product itself. It also makes provider-specific behavior—like rate limits and reported token usage—something the integration can handle explicitly.

But the product goal is still human-centered: bring relevant material back, help make connections easier to notice, and reduce the effort of recovering context. The system shouldn’t decide what an argument ought to be or what a writer should believe.

What kind of support helps you think more clearly without taking over? Is there a task you’d happily hand off—and one you’d always want to keep for yourself?

#HumanCenteredAI #Writing #Research
