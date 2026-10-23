# The scheduled design (Gemini Spark)

Spark schedules are stateless, so the whole pipeline is driven by one Google Sheet, the **tracker**. Each Seeq
resource is one row with a status per stage. One monthly schedule discovers new pages; four daily workers each pick
up the rows waiting at their stage, process a small batch and update the row. A worker with nothing waiting does
nothing, so the monthly refresh flows through on its own: new pages become new `Pending` rows.

Tracker columns, in order: `Section, Title, URL, Date Found, Publish Date, Extract Status, Notebook Name,
Notebook URL, Deck Status, Deck Link, Published, Notes` (a `Walkthrough Status` column was added in October 2026).

| # | Schedule | When | Picks | Cap per run | Does | Writes back |
|---|---|---|---|---|---|---|
| 0 | Monthly discovery | Monthly, day 1 | every resource section on seeq.com | none | adds one row per new page; never adds a URL twice; a page that no longer loads gets "Removed from site" in Notes, the row is kept | new rows, `Pending` |
| 1 | Extract to Doc | Daily 07:00 | `Extract Status = Pending`, newest first | 10 | reads the public page (and its tabs and linked detail pages; gated downloads are not opened) and appends a self-contained entry to the research Doc: summary in our own words, industry, problem, solution, Seeq tools used, results, related items | `Done` or `Failed` + reason |
| 2 | Build notebooks | Daily 09:00 | use cases with `Extract Status = Done` and no notebook | 3 | creates a NotebookLM notebook named `Seeq \| <title>` (the shared prefix is the grouping, since NotebookLM has no folders) with up to 15 sources: the page, its Doc entry, related Seeq items and up to 3 public pages on the engineering concept | notebook name and link; line in the index Doc |
| 3 | Generate decks | Daily 11:00 | rows with a notebook and no deck status | 3 | generates a 10–14 slide deck for first-year engineering students: context, problem, data concepts, the Seeq approach step by step, a worked example, impact, glossary, three check questions, what to study next | `Done` or `Failed` |
| 4 | Publish review page | Daily 14:00 | `Deck Status = Done` and not yet published | all | rebuilds one review page: contents by industry, a card per use case with summary and links, a Reviewed tick and a notes box | `Published = Yes` |

Every schedule: numbered steps, exact column order, one row per item, a cap per run, stop when nothing is waiting,
and end with a short confirmation with links.

## What happened when it ran

* Spark's task runner failed on manual runs, and Spark could not operate NotebookLM Studio ("automated access
  blocked by policy"). The tracker was therefore seeded from Seeq's sitemaps (424 resource pages; 83 use cases and
  17 success stories tracked) and the notebook, deck and walkthrough stages were run with a browser agent under
  my direction, using the same tracker and the same rules.
* A three-use-case pilot (pump health monitoring, golden-batch OEE, upstream well performance) came first. The
  notebooks were then grounded in the Seeq Knowledge Base page for every tool used, which led to the fifth stage:
  a step-by-step walkthrough per use case, with every Formula expression checked against the KB and labelled.
* `src/tracker/stages.py` is this state machine as code, so the rules can be tested and the schedule simulated.
