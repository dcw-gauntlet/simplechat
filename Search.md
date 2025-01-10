# Search

We want to support searching for messages.  A search request is a POST containing a search_query.

# Objects

SearchRequest
    search_query: str

SearchResponse
    messages: List[SearchResult]

SearchResult
    channel_id: str
    channel_name: str
    message: Message
    previous_message: Optional[Message]
    next_message: Optional[Message]
    score: float
