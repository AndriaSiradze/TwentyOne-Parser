from typing import TypedDict, Annotated

from pydantic import BaseModel, Field


class RelevanceCheck(BaseModel):
    """Checks article Relevance output model"""
    relevance: bool = Field(description='True if article is relevant to bitcoin')
    reason:str = Field(description='1 short sentence explaining why is article relevant or not ')


class SimilarityCheckResult(BaseModel):
    """Return result in Json format {'result': 'yes/no'}"""
    result: str = Field(description='yes/no')


class NewsParsingModel(BaseModel):
    """Returns result of parsing web page splited in 3 part title, body, tags """
    title: str = Field(description='Title of the article without any tags')
    body: str = Field(description='The whole content  excluding title and tags ')
    tags: list = Field(description='List of tags associated with this news each tag without #')


class NewsParsingModelRu(BaseModel):
    """Returns result in russian language of parsing web page splited in 3 part title_ru, body_ru, tags_ru """
    title_ru: str = Field(description='<b> Title of the article </b>  or <i/> if there not tag add')
    body_ru: str = Field(description='The whole content excluding title and tags ')
    tags_ru: list = Field(description='List of tags in ru language associated with this news each tag without #')

