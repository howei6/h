# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import datetime

import mock
import pytest
import sqlalchemy as sa
import transaction

from memex import models
from memex.models import document


class TestDocumentFindByURIs(object):

    def test_with_one_matching_Document(self, db_session):
        # One Document with a non-matching DocumentURI pointing to it.
        # find_by_uris() should not return this Document.
        document1 = document.Document()
        uri1 = 'https://de.wikipedia.org/wiki/Hauptseite'
        document1.document_uris.append(
            document.DocumentURI(claimant=uri1, uri=uri1))

        # A second Document with one matching and one non-matching DocumentURI
        # pointing to it. find_by_uris() should return this Document.
        document2 = document.Document()
        uri2 = 'https://en.wikipedia.org/wiki/Main_Page'
        document2.document_uris.append(
            document.DocumentURI(claimant=uri2, uri=uri2))
        uri3 = 'https://en.wikipedia.org'
        document2.document_uris.append(
            document.DocumentURI(claimant=uri3, uri=uri2))

        db_session.add_all([document1, document2])
        db_session.flush()

        actual = document.Document.find_by_uris(db_session, [
            'https://en.wikipedia.org/wiki/Main_Page',
            'https://m.en.wikipedia.org/wiki/Main_Page'])

        assert actual.count() == 1
        assert actual.first() == document2

    def test_no_matches(self, db_session):
        document_ = document.Document()
        document_.document_uris.append(document.DocumentURI(
            claimant='https://en.wikipedia.org/wiki/Main_Page',
            uri='https://en.wikipedia.org/wiki/Main_Page'))
        db_session.add(document_)
        db_session.flush()

        actual = document.Document.find_by_uris(
            db_session, ['https://de.wikipedia.org/wiki/Hauptseite'])
        assert actual.count() == 0


class TestDocumentFindOrCreateByURIs(object):

    def test_with_one_existing_Document(self, db_session):
        """
        When there's one matching Document it should return that Document.

        When searching with two URIs that match two DocumentURIs that both
        point to the same Document, it should return that Document.

        """
        document_ = document.Document()
        docuri1 = document.DocumentURI(
            claimant='https://en.wikipedia.org/wiki/Main_Page',
            uri='https://en.wikipedia.org/wiki/Main_Page',
            document=document_)
        docuri2 = document.DocumentURI(
            claimant='https://en.wikipedia.org/wiki/http/en.m.wikipedia.org/wiki/Main_Page',
            uri='https://en.wikipedia.org/wiki/Main_Page',
            document=document_)

        db_session.add(docuri1)
        db_session.add(docuri2)
        db_session.flush()

        actual = document.Document.find_or_create_by_uris(db_session,
            'https://en.wikipedia.org/wiki/Main_Page',
            ['https://en.wikipedia.org/wiki/http/en.m.wikipedia.org/wiki/Main_Page',
            'https://m.en.wikipedia.org/wiki/Main_Page'])

        assert actual.count() == 1
        assert actual.first() == document_

    def test_with_no_existing_documents(self, db_session):
        """When there are no matching Documents it creates and returns one."""
        document_ = document.Document()
        docuri = document.DocumentURI(
            claimant='https://en.wikipedia.org/wiki/Main_Page',
            uri='https://en.wikipedia.org/wiki/Main_Page',
            document=document_)

        db_session.add(docuri)
        db_session.flush()

        documents = document.Document.find_or_create_by_uris(
            db_session,
            'https://en.wikipedia.org/wiki/Pluto',
            ['https://m.en.wikipedia.org/wiki/Pluto'])

        assert documents.count() == 1

        actual = documents.first()
        assert isinstance(actual, document.Document)
        assert len(actual.document_uris) == 1

        docuri = actual.document_uris[0]
        assert docuri.claimant == 'https://en.wikipedia.org/wiki/Pluto'
        assert docuri.uri == 'https://en.wikipedia.org/wiki/Pluto'
        assert docuri.type == 'self-claim'

    def test_raises_retryable_error_when_flush_fails(self, db_session, monkeypatch):
        def err():
            raise sa.exc.IntegrityError(None, None, None)
        monkeypatch.setattr(db_session, 'flush', err)

        with pytest.raises(transaction.interfaces.TransientError):
            with db_session.no_autoflush:  # prevent premature IntegrityError
                document.Document.find_or_create_by_uris(
                    db_session,
                    'https://en.wikipedia.org/wiki/Pluto',
                    ['https://m.en.wikipedia.org/wiki/Pluto'])


class TestDocumentURI(object):

    def test_type_defaults_to_empty_string(self, db_session):
        document_uri = document.DocumentURI(claimant='http://www.example.com',
                                            uri='http://www.example.com',
                                            type=None,
                                            content_type='bar',
                                            document=document.Document())
        db_session.add(document_uri)

        db_session.flush()

        assert document_uri.type == ''

    def test_you_cannot_set_type_to_null(self, db_session):
        document_uri = document.DocumentURI(claimant='http://www.example.com',
                                            uri='http://www.example.com',
                                            type='foo',
                                            content_type='bar',
                                            document=document.Document())
        db_session.add(document_uri)
        db_session.flush()

        document_uri.type = None

        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()

    def test_content_type_defaults_to_empty_string(self, db_session):
        document_uri = document.DocumentURI(claimant='http://www.example.com',
                                            uri='http://www.example.com',
                                            type='bar',
                                            content_type=None,
                                            document=document.Document())
        db_session.add(document_uri)

        db_session.flush()

        assert document_uri.content_type == ''

    def test_you_cannot_set_content_type_to_null(self, db_session):
        document_uri = document.DocumentURI(claimant='http://www.example.com',
                                            uri='http://www.example.com',
                                            type='foo',
                                            content_type='bar',
                                            document=document.Document())
        db_session.add(document_uri)
        db_session.flush()

        document_uri.content_type = None

        with pytest.raises(sa.exc.IntegrityError):
            db_session.flush()

    def test_you_cannot_add_duplicate_document_uris(self, db_session):
        """
        You can't add duplicate DocumentURI's to the database.

        You can't add DocumentURI's with the same claimant, uri, type and
        content_type, even if they have different documents.

        """
        db_session.add_all([
            document.DocumentURI(claimant='http://www.example.com',
                                 uri='http://www.example.com',
                                 type='foo',
                                 content_type='bar',
                                 document=document.Document()),
            document.DocumentURI(claimant='http://www.example.com',
                                 uri='http://www.example.com',
                                 type='foo',
                                 content_type='bar',
                                 document=document.Document())
        ])

        with pytest.raises(sa.exc.IntegrityError):
            db_session.commit()


@pytest.mark.usefixtures(
    'log',
)
class TestCreateOrUpdateDocumentURI(object):

    def test_it_updates_the_existing_DocumentURI_if_there_is_one(self, db_session):
        claimant = 'http://example.com/example_claimant.html'
        uri = 'http://example.com/example_uri.html'
        type_ = 'self-claim'
        content_type = ''
        document_ = document.Document()
        created = yesterday()
        updated = yesterday()
        document_uri = document.DocumentURI(
            claimant=claimant,
            uri=uri,
            type=type_,
            content_type=content_type,
            document=document_,
            created=created,
            updated=updated,
        )
        db_session.add(document_uri)

        now_ = now()
        document.create_or_update_document_uri(
            session=db_session,
            claimant=claimant,
            uri=uri,
            type=type_,
            content_type=content_type,
            document=document_,
            created=now_,
            updated=now_,
        )

        assert document_uri.created == created
        assert document_uri.updated == now_
        assert len(db_session.query(document.DocumentURI).all()) == 1, (
            "It shouldn't have added any new objects to the db")

    def test_it_creates_a_new_DocumentURI_if_there_is_no_existing_one(self, db_session):
        claimant = 'http://example.com/example_claimant.html'
        uri = 'http://example.com/example_uri.html'
        type_ = 'self-claim'
        content_type = ''
        document_ = document.Document()
        created = yesterday()
        updated = yesterday()

        # Add one non-matching DocumentURI to the database.
        db_session.add(document.DocumentURI(
            claimant=claimant,
            uri=uri,
            type=type_,
            # Different content_type means this DocumentURI should not match
            # the query.
            content_type='different',
            document=document_,
            created=created,
            updated=updated,
        ))

        document.create_or_update_document_uri(
            session=db_session,
            claimant=claimant,
            uri=uri,
            type=type_,
            content_type=content_type,
            document=document_,
            created=now(),
            updated=now(),
        )

        document_uri = db_session.query(document.DocumentURI).all()[-1]
        assert document_uri.claimant == claimant
        assert document_uri.uri == uri
        assert document_uri.type == type_
        assert document_uri.content_type == content_type
        assert document_uri.document == document_
        assert document_uri.created > created
        assert document_uri.updated > updated

    def test_it_denormalizes_http_uri_to_document_when_none(self, db_session):
        uri = 'http://example.com/example_uri.html'

        document_ = document.Document(web_uri=None)
        db_session.add(document_)

        document.create_or_update_document_uri(
            session=db_session,
            claimant='http://example.com/example_claimant.html',
            uri=uri,
            type='self-claim',
            content_type='',
            document=document_,
            created=now(),
            updated=now(),
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.web_uri == uri

    def test_it_denormalizes_https_uri_to_document_when_empty(self, db_session):
        uri = 'https://example.com/example_uri.html'

        document_ = document.Document(web_uri='')
        db_session.add(document_)

        document.create_or_update_document_uri(
            session=db_session,
            claimant='http://example.com/example_claimant.html',
            uri=uri,
            type='self-claim',
            content_type='',
            document=document_,
            created=now(),
            updated=now(),
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.web_uri == uri

    def test_it_skips_denormalizing_http_s_uri_to_document(self, db_session):
        document_ = document.Document(web_uri='http://example.com/first_uri.html')
        db_session.add(document_)

        document.create_or_update_document_uri(
            session=db_session,
            claimant='http://example.com/example_claimant.html',
            uri='http://example.com/second_uri.html',
            type='self-claim',
            content_type='',
            document=document_,
            created=now(),
            updated=now(),
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.web_uri == 'http://example.com/first_uri.html'

    def test_it_logs_a_warning_if_document_ids_differ(self, log):
        """
        It should log a warning on Document objects mismatch.

        If there's an existing DocumentURI and its .document property is
        different to the given document it shoulg log a warning.

        """
        session = mock_db_session()

        # existing_document_uri.document won't be equal to the given document.
        existing_document_uri = mock.Mock(document=mock_document())
        session.query.return_value.filter.return_value.first.return_value = (
            existing_document_uri)

        document.create_or_update_document_uri(
            session=session,
            claimant='http://example.com/example_claimant.html',
            uri='http://example.com/example_uri.html',
            type='self-claim',
            content_type=None,
            document=mock_document(),
            created=now(),
            updated=now())

        assert log.warn.call_count == 1

    def test_raises_retryable_error_when_flush_fails(self, db_session, monkeypatch):
        document_ = document.Document()

        def err():
            raise sa.exc.IntegrityError(None, None, None)
        monkeypatch.setattr(db_session, 'flush', err)

        with pytest.raises(transaction.interfaces.TransientError):
            with db_session.no_autoflush:  # prevent premature IntegrityError
                document.create_or_update_document_uri(
                    session=db_session,
                    claimant='http://example.com',
                    uri='http://example.org',
                    type='rel-canonical',
                    content_type='text/html',
                    document=document_,
                    created=now(),
                    updated=now(),
                )


class TestCreateOrUpdateDocumentMeta(object):

    def test_it_creates_a_new_DocumentMeta_if_there_is_no_existing_one(self, db_session):
        claimant = 'http://example.com/claimant'
        type_ = 'title'
        value = 'the title'
        document_ = document.Document()
        created = yesterday()
        updated = now()

        # Add one non-matching DocumentMeta to the database.
        # This should be ignored.
        db_session.add(document.DocumentMeta(
            claimant=claimant,
            # Different type means this should not match the query.
            type='different',
            value=value,
            document=document_,
            created=created,
            updated=updated,
        ))

        document.create_or_update_document_meta(
            session=db_session,
            claimant=claimant,
            type=type_,
            value=value,
            document=document_,
            created=created,
            updated=updated,
        )

        document_meta = db_session.query(document.DocumentMeta).all()[-1]
        assert document_meta.claimant == claimant
        assert document_meta.type == type_
        assert document_meta.value == value
        assert document_meta.document == document_
        assert document_meta.created == created
        assert document_meta.updated == updated

    def test_it_updates_an_existing_DocumentMeta_if_there_is_one(self, db_session):
        claimant = 'http://example.com/claimant'
        type_ = 'title'
        value = 'the title'
        document_ = document.Document()
        created = yesterday()
        updated = now()
        document_meta = document.DocumentMeta(
            claimant=claimant,
            type=type_,
            value=value,
            document=document_,
            created=created,
            updated=updated,
        )
        db_session.add(document_meta)

        new_updated = now()
        document.create_or_update_document_meta(
            session=db_session,
            claimant=claimant,
            type=type_,
            value='new value',
            document=document.Document(),  # This should be ignored.
            created=now(),  # This should be ignored.
            updated=new_updated,
        )

        assert document_meta.value == 'new value'
        assert document_meta.updated == new_updated
        assert document_meta.created == created, "It shouldn't update created"
        assert document_meta.document == document_, (
            "It shouldn't update document")
        assert len(db_session.query(document.DocumentMeta).all()) == 1, (
            "It shouldn't have added any new objects to the db")

    def test_it_denormalizes_title_to_document_when_none(self, db_session):
        claimant = 'http://example.com/claimant'
        type_ = 'title'
        value = ['the title']
        document_ = document.Document(title=None)
        created = yesterday()
        updated = now()
        db_session.add(document_)

        document.create_or_update_document_meta(
            session=db_session,
            claimant=claimant,
            type=type_,
            value=value,
            document=document_,
            created=created,
            updated=updated,
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.title == value[0]

    def test_it_denormalizes_title_to_document_when_empty(self, db_session):
        claimant = 'http://example.com/claimant'
        type_ = 'title'
        value = ['the title']
        document_ = document.Document(title='')
        created = yesterday()
        updated = now()
        db_session.add(document_)

        document.create_or_update_document_meta(
            session=db_session,
            claimant=claimant,
            type=type_,
            value=value,
            document=document_,
            created=created,
            updated=updated,
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.title == value[0]

    def test_it_skips_denormalizing_title_to_document_when_already_set(self, db_session):
        claimant = 'http://example.com/claimant'
        type_ = 'title'
        value = ['the title']
        document_ = document.Document(title='foobar')
        created = yesterday()
        updated = now()
        db_session.add(document_)

        document.create_or_update_document_meta(
            session=db_session,
            claimant=claimant,
            type=type_,
            value=value,
            document=document_,
            created=created,
            updated=updated,
        )

        document_ = db_session.query(document.Document).get(document_.id)
        assert document_.title == 'foobar'

    def test_it_logs_a_warning(self, log):
        """
        It should warn on document mismatches.

        It should warn if there's an existing DocumentMeta with a different
        Document.

        """
        session = mock_db_session()
        document_one = mock_document()
        document_two = mock_document()
        existing_document_meta = mock_document_meta(document=document_one)
        session.query.return_value.filter.return_value.one_or_none\
            .return_value = existing_document_meta

        document.create_or_update_document_meta(
            session=session,
            claimant='http://example.com/claimant',
            type='title',
            value='new value',
            document=document_two,
            created=yesterday(),
            updated=now(),
        )

        assert log.warn.call_count == 1

    def test_raises_retryable_error_when_flush_fails(self, db_session, monkeypatch):
        document_ = document.Document()

        def err():
            raise sa.exc.IntegrityError(None, None, None)
        monkeypatch.setattr(db_session, 'flush', err)

        with pytest.raises(transaction.interfaces.TransientError):
            with db_session.no_autoflush:  # prevent premature IntegrityError
                document.create_or_update_document_meta(
                    session=db_session,
                    claimant='http://example.com',
                    type='title',
                    value='My Title',
                    document=document_,
                    created=now(),
                    updated=now(),
                )


@pytest.mark.usefixtures('merge_data')
class TestMergeDocuments(object):

    def test_merge_documents_returns_master(self, db_session, merge_data):
        master, _ = merge_data

        merged_master = document.merge_documents(db_session, merge_data)

        assert merged_master == master

    def test_merge_documents_deletes_duplicate_documents(self, db_session, merge_data):
        _, duplicate = merge_data

        document.merge_documents(db_session, merge_data)
        db_session.flush()

        assert db_session.query(document.Document).get(duplicate.id) is None

    def test_merge_documents_rewires_document_uris(self, db_session, merge_data):
        master, duplicate = merge_data

        document.merge_documents(db_session, merge_data)
        db_session.flush()

        assert len(master.document_uris) == 2
        assert len(duplicate.document_uris) == 0

    def test_merge_documents_rewires_document_meta(self, db_session, merge_data):
        master, duplicate = merge_data

        document.merge_documents(db_session, merge_data)
        db_session.flush()

        assert len(master.meta) == 2
        assert len(duplicate.meta) == 0

    def test_raises_retryable_error_when_flush_fails(self, db_session, merge_data, monkeypatch):
        def err():
            raise sa.exc.IntegrityError(None, None, None)
        monkeypatch.setattr(db_session, 'flush', err)

        with pytest.raises(transaction.interfaces.TransientError):
            document.merge_documents(db_session, merge_data)

    @pytest.fixture
    def merge_data(self, db_session, request):
        master = document.Document(document_uris=[document.DocumentURI(
                claimant='https://en.wikipedia.org/wiki/Main_Page',
                uri='https://en.wikipedia.org/wiki/Main_Page',
                type='self-claim')],
                meta=[document.DocumentMeta(
                    claimant='https://en.wikipedia.org/wiki/Main_Page',
                    type='title',
                    value='Wikipedia, the free encyclopedia')])
        duplicate = document.Document(document_uris=[document.DocumentURI(
                claimant='https://m.en.wikipedia.org/wiki/Main_Page',
                uri='https://en.wikipedia.org/wiki/Main_Page',
                type='rel-canonical')],
                meta=[document.DocumentMeta(
                    claimant='https://m.en.wikipedia.org/wiki/Main_Page',
                    type='title',
                    value='Wikipedia, the free encyclopedia')])

        db_session.add_all([master, duplicate])
        db_session.flush()
        return (master, duplicate)


class TestUpdateDocumentMetadata(object):

    def test_it_uses_the_target_uri_to_get_the_document(self,
                                                        annotation,
                                                        Document,
                                                        session):
        document_uri_dicts = [
            {
                'uri': 'http://example.com/example_1',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
            {
                'uri': 'http://example.com/example_2',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
            {
                'uri': 'http://example.com/example_3',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
        ]

        document.update_document_metadata(session,
                                          annotation,
                                          [],
                                          document_uri_dicts)

        Document.find_or_create_by_uris.assert_called_once_with(
            session,
            annotation.target_uri,
            [
                'http://example.com/example_1',
                'http://example.com/example_2',
                'http://example.com/example_3',
            ],
            created=annotation.created,
            updated=annotation.updated,
        )

    def test_if_there_are_multiple_documents_it_merges_them_into_one(
            self,
            annotation,
            Document,
            merge_documents,
            session):
        """If it finds more than one document it calls merge_documents()."""
        Document.find_or_create_by_uris.return_value = mock.Mock(
            count=mock.Mock(return_value=3))

        document.update_document_metadata(session, annotation, [], [])

        merge_documents.assert_called_once_with(
            session,
            Document.find_or_create_by_uris.return_value,
            updated=annotation.updated)

    def test_it_calls_first(self, annotation, session, Document):
        """If it finds only one document it calls first()."""
        Document.find_or_create_by_uris.return_value = mock.Mock(
            count=mock.Mock(return_value=1))

        document.update_document_metadata(session, annotation, [], [])

        Document.find_or_create_by_uris.return_value\
            .first.assert_called_once_with()

    def test_it_updates_document_updated(self,
                                         annotation,
                                         Document,
                                         merge_documents,
                                         session):
        yesterday_ = "yesterday"
        document_ = merge_documents.return_value = mock.Mock(
            updated=yesterday_)
        Document.find_or_create_by_uris.return_value.first.return_value = (
            document_)

        document.update_document_metadata(session, annotation, [], [])

        assert document_.updated == annotation.updated

    def test_it_saves_all_the_document_uris(self,
                                            session,
                                            annotation,
                                            Document,
                                            create_or_update_document_uri):
        """It creates or updates a DocumentURI for each document URI dict."""
        Document.find_or_create_by_uris.return_value.count.return_value = 1

        document_uri_dicts = [
            {
                'uri': 'http://example.com/example_1',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
            {
                'uri': 'http://example.com/example_2',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
            {
                'uri': 'http://example.com/example_3',
                'claimant': 'http://example.com/claimant',
                'type': 'type',
                'content_type': None,
            },
        ]

        document.update_document_metadata(session,
                                          annotation,
                                          [],
                                          document_uri_dicts)

        assert create_or_update_document_uri.call_count == 3
        for doc_uri_dict in document_uri_dicts:
            create_or_update_document_uri.assert_any_call(
                session=session,
                document=Document.find_or_create_by_uris.return_value.first.return_value,
                created=annotation.created,
                updated=annotation.updated,
                **doc_uri_dict
            )

    def test_it_saves_all_the_document_metas(self,
                                             annotation,
                                             create_or_update_document_meta,
                                             Document,
                                             session):
        """It creates or updates a DocumentMeta for each document meta dict."""
        Document.find_or_create_by_uris.return_value.count\
            .return_value = 1

        document_meta_dicts = [
            {
                'claimant': 'http://example.com/claimant',
                'type': 'title',
                'value': 'foo',
            },
            {
                'type': 'article title',
                'value': 'bar',
                'claimant': 'http://example.com/claimant',
            },
            {
                'type': 'site title',
                'value': 'gar',
                'claimant': 'http://example.com/claimant',
            },
        ]

        document.update_document_metadata(session,
                                          annotation,
                                          document_meta_dicts,
                                          [])

        assert create_or_update_document_meta.call_count == 3
        for document_meta_dict in document_meta_dicts:
            create_or_update_document_meta.assert_any_call(
                session=session,
                document=Document.find_or_create_by_uris.return_value.first.return_value,
                created=annotation.created,
                updated=annotation.updated,
                **document_meta_dict
            )

    @pytest.fixture
    def annotation(self):
        return mock.Mock(spec=models.Annotation())

    @pytest.fixture
    def create_or_update_document_meta(self, patch):
        return patch('memex.models.document.create_or_update_document_meta')

    @pytest.fixture
    def create_or_update_document_uri(self, patch):
        return patch('memex.models.document.create_or_update_document_uri')

    @pytest.fixture
    def Document(self, patch):
        return patch('memex.models.document.Document')

    @pytest.fixture
    def merge_documents(self, patch):
        return patch('memex.models.document.merge_documents')

    @pytest.fixture
    def session(self, db_session):
        return mock.Mock(spec=db_session)


def now():
    return datetime.datetime.now()


def yesterday():
    return now() - datetime.timedelta(days=1)


def mock_db_session():
    """Return a mock db session object."""
    class DB(object):
        def add(self, obj):
            pass
        def query(self, cls):
            pass
        def flush(self):
            pass
    return mock.Mock(spec=DB())


def mock_document():
    """Return a mock Document object."""
    return mock.Mock(spec=document.Document())


def mock_document_meta(document=None):

    # We define a class to use as the mock spec here because we can't use the
    # real DocumentMeta class because that class may be patched in the tests
    # that are calling this function (so we'd end up using a mock object as a
    # spec instead, and get completely the wrong spec).
    class DocumentMeta(object):
        def __init__(self):
            self.type = None
            self.value = None
            self.created = None
            self.updated = None
            self.document = document
            self.id = None
            self.document_id = None

    return mock.Mock(spec=DocumentMeta())


@pytest.fixture
def log(patch):
    return patch('memex.models.document.log')
