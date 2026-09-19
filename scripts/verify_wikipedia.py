"""Explicit live acceptance test: paid APIs; never imported by offline pytest."""
import json
import os
from urllib.parse import unquote

from jev_ultrafast import Agent

assert os.environ.get("JEV_PROVIDER") == "vercel", "Acceptance requires JEV_PROVIDER=vercel"

with Agent(
    "https://en.wikipedia.org/wiki/Main_Page",
    "Search Wikipedia for Gödel's incompleteness theorems, open the article, and confirm its title.",
) as agent:
    for state in agent.run():
        print(json.dumps({"status": state["status"], "elapsed_ms": state["elapsed_ms"]}), flush=True)
    # Read the actual browser document independently; DONE alone does not pass.
    actual = agent.browser.evaluate(
        "({title:document.title,url:location.href,heading:document.querySelector('h1')?.innerText})"
    )
    assert actual["heading"] == "Gödel's incompleteness theorems", actual
    assert unquote(actual["url"]).endswith("/wiki/Gödel's_incompleteness_theorems"), actual
    assert actual["title"] == "Gödel's incompleteness theorems - Wikipedia", actual
    assert agent.state["text_calls"], "This run did not exercise TYPE_TEXT; helper acceptance is incomplete"
    print(json.dumps({"verified": True, "decision_calls": len(agent.state["decisions"]),
                      "text_calls": len(agent.state["text_calls"]), **actual}, ensure_ascii=False))
