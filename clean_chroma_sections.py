from api.chroma import collection
from make_embeddings import Article, Section, collection, session_scope


def clean_chroma_sections():
    # delete any sections in chroma for articles that no longer exist
    with session_scope() as db_session:
        existing_articles = db_session.query(Article).all()
        existing_article_ids = {a.id for a in existing_articles}
        existing_sections = db_session.query(Section).all()

        removed_sections = []
        for section in existing_sections:
            if section.article_id not in existing_article_ids:
                removed_sections.append(section.checksum)

        if removed_sections:
            collection.delete(ids=removed_sections)
            print(f"Removed sections: {removed_sections}")


if __name__ == "__main__":
    clean_chroma_sections()
