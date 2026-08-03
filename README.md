\## Synthetic demonstration data



The project includes a configurable synthetic retail data generator.



The generated dataset reproduces several business patterns:



\- weekly and annual seasonality;

\- growing and declining product demand;

\- promotional effects;

\- supplier lead times and delays;

\- inventory replenishment;

\- stockouts and unmet demand;

\- slow-moving and high-volume products;

\- multiple stores, products and suppliers.



The dataset is intended for development, testing and demonstration.



It does not represent guaranteed model performance on a real business.

A production deployment requires client-specific data validation,

backtesting and calibration.



\### Generate the dataset



```bash

python ml/data\_generation/generate\_retail\_data.py \\

&#x20; --start-date 2024-01-01 \\

&#x20; --days 730 \\

&#x20; --products 120 \\

&#x20; --stores 2 \\

&#x20; --suppliers 8 \\

&#x20; --seed 42

