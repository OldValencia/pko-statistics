-- City or place as the bank reports it (push "Place: <merchant>, <city>", CSV "Miasto").
ALTER TABLE transactions ADD COLUMN location TEXT;
