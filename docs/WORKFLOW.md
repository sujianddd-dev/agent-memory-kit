# From suggestion to change

What happens when someone (a human, another agent, a broadcast reply) gives us a
suggestion:

1. **Judge** — is it concrete, reproducible, and relevant to something we run?
2. **Try** — reproduce it locally, even if the change is small. No "sounds good"
   without an attempt.
3. **Record** — write the outcome into memory: fact in mem0, knowledge note in
   Obsidian, with the source (thread / item id).
4. **Ship** — if the attempt worked, open an issue or PR on the repo that owns
   the behavior, link the evidence, and keep the commit small.
5. **Reply** — answer the original thread with what changed (or why it did not),
   including the link.

The rule that matters: **a suggestion that does not become an attempt is not
accepted**. An attempt that does not become a commit, issue, or note did not
happen.

`kit/suggestion_to_issue.py` is the smallest possible implementation of step 4:
it opens one issue with the suggestion plus the local attempt summary.
