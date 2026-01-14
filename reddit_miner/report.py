from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def print_report_rich(*, summary: dict, rows: list[tuple], top_n: int):
    # rows: (ticker, bullish, bearish, neutral, mentions, score)
    console = Console()

    lines = [
        f"DB: {summary['db_path']}",
        f"Subreddits: {', '.join(summary['subreddits'])}",
        f"Listing: {summary['listing']} | Posts/sub: {summary['post_limit']} | Max comments/post: {summary['max_comments_per_post']}",
        f"Analysis tag: {summary['analysis_tag']} | Model: {summary['model']}",
        f"Comments saved (this run): {summary.get('saved', '-')}",
        f"Comments model-called (this run): {summary.get('analyzed_model_calls', '-')}",
    ]
    console.print(Panel("\n".join(lines), title="Run summary", expand=False))

    table = Table(title=f"Ticker sentiment (Top {top_n})", show_lines=False)
    table.add_column("Ticker", justify="left", no_wrap=True)
    table.add_column("Bull", justify="right")
    table.add_column("Bear", justify="right")
    table.add_column("Neut", justify="right")
    table.add_column("Mentions", justify="right")
    table.add_column("Score", justify="right")

    for (ticker, bull, bear, neu, mentions, score) in rows[:top_n]:
        score_text = Text(str(score))
        if score > 0:
            score_text.stylize("green")
        elif score < 0:
            score_text.stylize("red")
        else:
            score_text.stylize("yellow")

        table.add_row(str(ticker), str(bull), str(bear), str(neu), str(mentions), score_text)

    console.print(table)
