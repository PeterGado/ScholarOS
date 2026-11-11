# Day 24

The next milestone for ScholarOS isn’t just adding another feature.

The production setup today is a React frontend on Vercel, a FastAPI backend on Fly.io, and PostgreSQL on Neon. The backend runs on two Fly machines; database migrations run once as a release command before the new version receives traffic.

That’s a real deployment topology, not a claim of unlimited scale. The app and its Work Item executor run together on each backend machine, and PostgreSQL coordinates which worker claims a queued item.

The next product challenge is still making the journey from source material to useful work feel more connected. Infrastructure keeps the system running; it doesn’t decide which workflow is worth building.

If you could improve one step in your research-to-writing workflow, which would you choose—and what makes it frustrating today?

#BuildInPublic #ProductDesign #Research
