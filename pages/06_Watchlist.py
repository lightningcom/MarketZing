from navigation import render_secondary_page


render_secondary_page(
	"Watchlist",
	"Search your stock",
	"Your saved indices and instruments will appear here once a watchlist is configured.",
	[
		("Indices", "Saved market indices."),
		("Stocks", "Saved companies and their latest moves."),
		("Alerts", "Price and performance levels to monitor."),
	],
)
