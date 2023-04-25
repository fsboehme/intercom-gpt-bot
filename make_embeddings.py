import argparse
import ast
import asyncio
from contextlib import contextmanager
import hashlib
from typing import Any, Dict, List
from bs4 import BeautifulSoup

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from api.chroma import collection
from api.openai import get_embedding

Base = declarative_base()

engine = create_engine("sqlite:///articles.db")
Session = sessionmaker(bind=engine)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    body = Column(String)
    url = Column(String)
    updated_at = Column(Integer)


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    checksum = Column(String)
    content = Column(Text)
    embedding = Column(Text)


@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def store_articles(articles: List[Dict[str, Any]]):
    updated_articles = []

    with session_scope() as db_session:
        Base.metadata.create_all(engine)
        for article in articles:
            if not article["body"] or article["state"] != "published":
                continue

            existing_article = (
                db_session.query(Article).filter(Article.id == article["id"]).first()
            )

            if not existing_article:
                new_article = Article(
                    id=article["id"],
                    title=article["title"],
                    description=article["description"],
                    body=article["body"],
                    url=article["url"],
                    updated_at=article["updated_at"],
                )
                db_session.add(new_article)
                updated_articles.append(article)

            elif existing_article.updated_at < article["updated_at"]:
                existing_article.title = article["title"]
                existing_article.description = article["description"]
                existing_article.body = article["body"]
                existing_article.url = article["url"]
                existing_article.updated_at = article["updated_at"]
                updated_articles.append(article)

    return updated_articles


def make_sections(article):
    """
    Split an article into sections based on headers
    returns a list of strings
    """
    import re

    sections = []
    partial_section = ""
    # split by headers
    for section in re.split(r"(<h[1-3][^>]*>.*?</h[1-3]>)", article["body"]):
        # if section is not empty and not just whitespace
        if section and not section.isspace():
            # if section starts with a header
            if section.startswith("<h"):
                # if we have a partial section, merge it with the current section
                if partial_section:
                    partial_section += section
                # if we don't have a partial section, save it for later
                else:
                    partial_section = section
            # if section doesn't start with a header
            else:
                # if we have a partial section, merge it with the current section
                if partial_section:
                    section = partial_section + section
                    partial_section = ""

                # remove <hr> tags at the beginning or end of a section
                section = re.sub(r"^<hr>", "", section)
                section = re.sub(r"<hr>$", "", section)

                sections.append(section)
    # Add any remaining partial_section to the last section
    if partial_section and sections:
        sections[-1] += partial_section
    return sections


def clean_sections(sections):
    """
    Remove empty paragraphs and whitespace from sections
    """
    cleaned_sections = []
    for section in sections:
        cs = clean_html(section)
        if cs:
            cleaned_sections.append(cs)
    return cleaned_sections


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove class and id attributes
    for tag in soup():
        if "class" in tag.attrs:
            del tag.attrs["class"]
        if "id" in tag.attrs:
            del tag.attrs["id"]

    # Remove empty paragraphs
    for p in soup.find_all("p"):
        if not p.get_text(strip=True):
            p.decompose()

    # Minify: remove all whitespace
    minified_html = "".join(line.strip() for line in str(soup).split("\n"))

    return minified_html


def get_annotation(article: dict):
    title = article["title"]
    description = article["description"]
    url = article["url"]
    annotation = "<p><em>Excerpt from "
    if description:
        annotation += f'<a href="{url}" target="_blank">{title} - {description}</a>'
    else:
        annotation += f'<a href="{url}" target="_blank">{title}</a>'
    annotation += "</em></p>"

    return annotation


def annotate_sections(sections, article: dict):
    annotation = get_annotation(article)
    annotated_sections = []
    for section in sections:
        annotated_sections.append(section + annotation)
    return annotated_sections


def generate_checksum(section):
    return hashlib.md5(section.encode("utf-8")).hexdigest()


def store_sections(sections: List[str], article: dict):
    sections = annotate_sections(clean_sections(sections), article)
    article_id = article["id"]
    # Use the context manager to handle the session
    with session_scope() as db_session:
        # Get existing sections for the article
        existing_sections = (
            db_session.query(Section).filter(Section.article_id == article_id).all()
        )

        # Initialize helper variables
        matched_existing_sections = []
        removed_sections = []
        embeddings = []
        metadatas = []
        ids = []

        # Step through the sections
        for section in sections:
            # Generate the checksum for the section
            checksum = generate_checksum(section)

            # If a section with the same checksum already exists, skip it and mark for removal
            if any([checksum == s.checksum for s in existing_sections]):
                matched_existing_sections.append(checksum)
                # make sure it also exists in chroma
                if not collection.get(checksum)["ids"]:
                    # retrieve existing section from db and add to chroma
                    existing_section = (
                        db_session.query(Section).filter_by(checksum=checksum).first()
                    )

                    embedding = ast.literal_eval(
                        existing_section.embedding
                    ) or get_embedding(section)
                    collection.add(
                        embeddings=[embedding],
                        metadatas=[{"article_id": article_id}],
                        ids=[checksum],
                    )
                continue

            # If section with the same checksum does not exist, generate the embedding and save it
            embedding = get_embedding(section)
            new_section = Section(
                article_id=article_id,
                checksum=checksum,
                content=section,
                embedding=str(embedding),
            )
            # Save to the database
            db_session.add(new_section)

            # Add to lists for chroma
            embeddings.append(embedding)
            metadatas.append({"article_id": article_id})
            ids.append(checksum)

        # Delete sections that no longer exist
        for existing_section in existing_sections:
            if existing_section.checksum not in matched_existing_sections:
                # add for removal from chroma if it exists there
                if collection.get(existing_section.checksum):
                    removed_sections.append(existing_section.checksum)
                # Delete from the database
                db_session.delete(existing_section)

        # Delete removed sections from chroma
        if removed_sections:
            collection.delete(ids=removed_sections)

    # Add the new sections to chroma
    if ids:
        collection.add(embeddings=embeddings, metadatas=metadatas, ids=ids)


async def make_embeddings(force_update=False):
    from api.intercom import get_all_articles

    articles = await get_all_articles()
    # from sample_data import articles

    updated_articles = store_articles(articles)
    print(f"Updated articles: {len(updated_articles)}")

    loop_articles = updated_articles
    if force_update:
        loop_articles = [
            article
            for article in articles
            if article["body"] and article["state"] == "published"
        ]

    for article in loop_articles:
        print(f'Article: {article["title"]} - {article["url"]}')
        sections = make_sections(article)
        print(f"Sections: {len(sections)}")
        store_sections(sections, article)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update stored articles.")
    parser.add_argument(
        "--force_update",
        action="store_true",
        help="process sections from all articles, modified or not",
    )
    args = parser.parse_args()

    # run the main coroutine with asyncio.run()
    asyncio.run(make_embeddings(args.force_update))
