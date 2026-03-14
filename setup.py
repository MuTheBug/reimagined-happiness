from setuptools import setup, find_packages

setup(
    name="binance-grid-trading-bot",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "python-binance>=1.0.19",
        "pydantic>=2.0",
        "pydantic-settings>=2.0",
    ],
    package_data={
        "grid_trading_bot": ["static/*.html"],
    },
    entry_points={
        "console_scripts": [
            "grid-bot=grid_trading_bot.main:main",
            "grid-scanner=grid_trading_bot.web_scanner:main",
        ],
    },
)
