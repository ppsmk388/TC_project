from typing import List, Dict, Any

from .llm import llm_chat


def fetch_tweets(usernames: List[str], n_per_user: int = 20) -> List[Dict[str, Any]]:
    tweets: List[Dict[str, Any]] = []
    try:
        import snscrape.modules.twitter as sntwitter
    except Exception:
        return tweets
    for u in usernames:
        try:
            for i, t in enumerate(sntwitter.TwitterUserScraper(u).get_items()):
                tweets.append({
                    "user": u,
                    "date": getattr(t, "date", None),
                    "content": getattr(t, "rawContent", ""),
                    "url": f"https://x.com/{u}/status/{t.id}",
                })
                if i + 1 >= n_per_user:
                    break
        except Exception:
            continue
    return tweets


def summarize_trends(tweets: List[Dict[str, Any]]) -> str:
    corpus = "\n".join([f"- {t['user']}: {t['content']}" for t in tweets])
    system = (
        "You are an analyst. Summarize recent themes, emerging topics, and any named entities (people, venues, datasets) from the tweets. "
        "Return: 1) 5 bullet trends with short evidence snippets; 2) Watchlist (3-5 items); 3) One-paragraph take."
    )
    return llm_chat(system, corpus)


