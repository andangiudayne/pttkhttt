from chobay.dao.database import Database
from chobay.dao.interfaces import SearchLogDAO
from chobay.model.search_log import SearchLog


class SearchLogDAOImpl(SearchLogDAO):
    def __init__(self, db: Database):
        self.db = db

    def save(self, log: SearchLog) -> int:
        with self.db.connect() as con:
            cur = con.execute("INSERT INTO search_log(customer_id, mode, query, top_product_id) VALUES (?,?,?,?)",
                              (log.customer_id, log.mode, log.query, log.top_product_id))
            log.log_id = cur.lastrowid
        return log.log_id

    def find_recent(self, customer_id: int, limit: int = 5) -> list[SearchLog]:
        with self.db.connect() as con:
            rows = con.execute("""SELECT * FROM search_log WHERE customer_id = ? AND mode != 'IMAGE'
                                  AND log_id IN (SELECT MAX(log_id) FROM search_log WHERE customer_id = ? GROUP BY query)
                                  ORDER BY log_id DESC LIMIT ?""", (customer_id, customer_id, limit)).fetchall()
        return [SearchLog(r["customer_id"], r["mode"], r["query"], r["top_product_id"], r["log_id"], r["ts"]) for r in rows]
