# Five-minute product demo

1. Open the Gatherly frontend and point out event search, availability badges, and responsive cards.
2. Open **AWS Workshop Accra 2026**, enter a name/email, and submit the registration form.
3. Show the confirmation ticket ID and print-friendly ticket screen.
4. Use **My registrations** with the same email; explain that the API returns only ticket metadata, not a registrant profile.
5. Cancel the registration, confirm the dialog, and refresh the event to show capacity restored.
6. In AWS, show the SAM stack, two DynamoDB tables, Lambda JSON logs/X-Ray traces, and the four CloudWatch alarms.
7. Trigger or discuss two simultaneous registrations for one remaining seat: DynamoDB's transaction conditional expression ensures one succeeds and one receives `EVENT_UNAVAILABLE`.
8. Show the GitHub Actions run: test/lint/SAM build/frontend build, then OIDC deployment and API smoke test.

For a live deployment, seed `events/sample-events.json` after stack creation before beginning step 1.
