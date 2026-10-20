from navigation import render_secondary_page


render_secondary_page(
	"Funds",
	"Funds",
	"Fund flows, categories, and holdings will appear here as data sources are added.",
	[
		("Mutual fund flows", "Subscriptions and redemptions by category."),
		("Index funds & ETFs", "Passive products, assets, and costs."),
		("Fund ownership", "Who invests in funds and where they are based."),
		("Portfolio managers", "Managed portfolios and investor composition."),
	],
)
