# The Catalyst Synthesizer

Here is the transcript of $TICKER's latest earnings call.

<transcript>
{{PASTE TRANSCRIPT}}
</transcript>

1. Summarise the top 3 bullish and top 3 bearish points. For each: the point, the exact evidence
   (quote the number and speaker where possible), and the category (guidance, demand, margins,
   capital_return, product, balance_sheet, other). Do not invent figures.
2. Rate the overall tone from -1 (very bearish) to +1 (very bullish).
3. List the dated catalysts management mentioned (product launches, investor days, regulatory decisions).
4. Cross-reference with insider Form 4 activity over the last 30 days:

<insider_activity>
{{PASTE OUTPUT OF: centaur catalyst --ticker TICKER}}
</insider_activity>

   Do the words and the money agree? Insiders buying into a bullish call CONFIRMS; insiders selling into a
   bullish call CONTRADICTS - say which and weigh the money over the words.
5. Output: one fundamental signal and (if warranted) one sentiment_flow signal in the
   "category: description" format, plus a one-line thesis.

Structured version: `centaur catalyst --ticker TICKER --transcript call.txt` does steps 1-4 with strict JSON output.
