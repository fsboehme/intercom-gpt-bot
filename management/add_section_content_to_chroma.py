import asyncio
import json
from termcolor import cprint
from api.chroma import collection
from make_embeddings import Article, Section, collection, make_embeddings, session_scope


def add_section_content_to_chroma():
    """
    Adds the Section.content as the documents value in Chroma for all sections in the db
    """
    with session_scope() as db_session:
        # Get all sections from the database
        sections = db_session.query(Section).all()
        force_update_article_ids = []

        for section in sections:
            # Find the corresponding entry in the Chroma collection by id (Section.checksum)
            chroma_entry = collection.get(section.checksum)

            if chroma_entry["ids"]:
                # get the article url as source
                article = (
                    db_session.query(Article)
                    .filter(Article.id == section.article_id)
                    .first()
                )

                # Add the Section.content as the documents value in Chroma
                collection.update(
                    ids=section.checksum,
                    embeddings=json.loads(section.embedding),
                    documents=section.content,
                    metadatas={"article_id": section.article_id, "source": article.url},
                )
                cprint(f"Added content for section: {section.content[:100]}", "green")
            else:
                force_update_article_ids.append(section.article_id)
                cprint(
                    f"{section.article_id} No Chroma entry found for section: {section.content[:100]}",
                    "red",
                )
        print(f"Articles out of sync: {force_update_article_ids}")
        if force_update_article_ids:
            asyncio.run(make_embeddings(force_update_article_ids))


if __name__ == "__main__":
    add_section_content_to_chroma()
