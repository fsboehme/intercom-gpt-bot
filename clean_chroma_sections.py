from termcolor import cprint
from api.chroma import collection
from make_embeddings import Article, Section, collection, session_scope


def clean_chroma_sections():
    """
    deletes any sections in chroma for articles that no longer exist in the db
    """
    with session_scope() as db_session:
        # Get all sections whose article_id does not exist in the Article table
        subquery = (
            db_session.query(Article.id)
            .filter(Article.id == Section.article_id)
            .exists()
        )
        non_existent_sections = db_session.query(Section).filter(~subquery).all()

        removed_sections = []
        for section in non_existent_sections:
            if collection.get(section.checksum)["ids"]:
                cprint(f"Removing section: {section.content[:100]}", "blue")
                removed_sections.append(section.checksum)
            else:
                # delete from db
                db_session.delete(section)

        if removed_sections:
            collection.delete(ids=removed_sections)
            cprint(f"Removed sections: {len(removed_sections)}", "red")
        else:
            cprint(f"No sections to remove", "green")


if __name__ == "__main__":
    clean_chroma_sections()
