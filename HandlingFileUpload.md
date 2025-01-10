# Handling File Uploads

We want to support file uploads for user messages.  A user should be able to attach a file as part of a message.  From the client's perspective this will look like:
1. Upload a file and get a file id back
2. Send a message with the file id

To support this we need to support a file upload endpoint on the server that accepts a file, stores the binary of the file in the database, and returns a file id.  We also need to support a file download endpoint that allows a user to download a file by file id.