# Copyright (C) 2016 Dmitry Marakasov <amdmi3@amdmi3.ru>
#
# This file is part of repology
#
# repology is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# repology is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with repology.  If not, see <http://www.gnu.org/licenses/>.

import psycopg2
import sys

from repology.package import Package


class QueryFilter():
    def GetWhere(self):
        return None

    def GetWhereArgs(self):
        return []

    def GetHaving(self):
        return None

    def GetHavingArgs(self):
        return []

    def GetSort(self):
        return None


class NameStartingQueryFilter(QueryFilter):
    def __init__(self, name=None):
        self.name = name

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return 'effname >= %s' if self.name else 'true'

    def GetWhereArgs(self):
        return [ self.name ] if self.name else []

    def GetSort(self):
        return 'effname ASC'


class NameAfterQueryFilter(QueryFilter):
    def __init__(self, name=None):
        self.name = name

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return 'effname > %s' if self.name else 'true'

    def GetWhereArgs(self):
        return [ self.name ] if self.name else []

    def GetSort(self):
        return 'effname ASC'


class NameBeforeQueryFilter(QueryFilter):
    def __init__(self, name=None):
        self.name = name

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return 'effname < %s' if self.name else 'true'

    def GetWhereArgs(self):
        return [ self.name ] if self.name else []

    def GetSort(self):
        return 'effname DESC'


class NameSubstringQueryFilter(QueryFilter):
    def __init__(self, name):
        self.name = name

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return '{table}.effname like %s'

    def GetWhereArgs(self):
        return [ self.name + "%" ]


class MaintainerQueryFilter(QueryFilter):
    def __init__(self, maintainer):
        self.maintainer = maintainer

    def GetTable(self):
        return 'maintainer_metapackages'

    def GetWhere(self):
        return '{table}.maintainer=%s'

    def GetWhereArgs(self):
        return [ self.maintainer ]


class MaintainerOutdatedQueryFilter(QueryFilter):
    def __init__(self, maintainer):
        self.maintainer = maintainer

    def GetTable(self):
        return 'maintainer_metapackages'

    def GetWhere(self):
        return '{table}.maintainer=%s and {table}.num_packages_outdated > 0'

    def GetWhereArgs(self):
        return [ self.maintainer ]


class InRepoQueryFilter(QueryFilter):
    def __init__(self, repo):
        self.repo = repo

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return '{table}.repo=%s'

    def GetWhereArgs(self):
        return [ self.repo ]


class InAnyRepoQueryFilter(QueryFilter):
    def __init__(self, repos):
        self.repos = repos

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return '{table}.repo in (' + ','.join(['%s'] * len(self.repos)) + ')'

    def GetWhereArgs(self):
        return [ repo for repo in self.repos ]


class InNumReposQueryFilter(QueryFilter):
    def __init__(self, more=None, less=None):
        self.more = more
        self.less = less

    def GetTable(self):
        return 'metapackage_repocounts'

    def GetWhere(self):
        conditions = []
        if self.more is not None:
            conditions.append("{table}.num_repos >= %s")
        if self.less is not None:
            conditions.append("{table}.num_repos <= %s")

        return ' AND '.join(conditions)

    def GetWhereArgs(self):
        args = []
        if self.more is not None:
            args.append(self.more)
        if self.less is not None:
            args.append(self.less)

        return args


class InNumFamiliesQueryFilter(QueryFilter):
    def __init__(self, more=None, less=None):
        self.more = more
        self.less = less

    def GetTable(self):
        return 'metapackage_repocounts'

    def GetWhere(self):
        conditions = []
        if self.more is not None:
            conditions.append("{table}.num_families >= %s")
        if self.less is not None:
            conditions.append("{table}.num_families <= %s")

        return ' AND '.join(conditions)

    def GetWhereArgs(self):
        args = []
        if self.more is not None:
            args.append(self.more)
        if self.less is not None:
            args.append(self.less)

        return args


class OutdatedInRepoQueryFilter(QueryFilter):
    def __init__(self, repo):
        self.repo = repo

    def GetTable(self):
        return 'repo_metapackages'

    def GetWhere(self):
        return '{table}.repo=%s AND {table}.num_outdated>0'

    def GetWhereArgs(self):
        return [ self.repo ]


class NotInRepoQueryFilter(QueryFilter):
    def __init__(self, repo):
        self.repo = repo

    def GetTable(self):
        return 'repo_metapackages'

    def GetHaving(self):
        return 'count(nullif({table}.repo = %s, false)) = 0'

    def GetHavingArgs(self):
        return [ self.repo ]


class MetapackageQueryConstructor:
    def __init__(self, *filters, limit=500):
        self.filters = filters
        self.limit = limit

    def GetQuery(self):
        tables = []
        where = []
        where_args = []
        having = []
        having_args = []
        args = []
        sort = None

        tablenum = 0
        for f in self.filters:
            tableid = '{}{}'.format(f.GetTable(), str(tablenum))

            tables.append('{} AS {}'.format(f.GetTable(), tableid))

            if f.GetWhere():
                where.append(f.GetWhere().format(table=tableid))
                where_args += f.GetWhereArgs()

            if f.GetHaving():
                having.append(f.GetHaving().format(table=tableid))
                having_args += f.GetHavingArgs()

            if f.GetSort():
                if sort is None:
                    sort = f.GetSort()
                elif sort == f.GetSort():
                    pass
                else:
                    raise RuntimeError("sorting mode conflict in query")

            tablenum += 1

        query = 'SELECT DISTINCT effname FROM '

        query += tables[0]
        for table in tables[1:]:
            query += ' INNER JOIN {} USING(effname)'.format(table)

        if where:
            query += ' WHERE '
            query += ' AND '.join(where)
            args += where_args

        if having:
            query += ' GROUP BY effname HAVING ' + ' AND '.join(having)
            args += having_args

        if sort:
            query += ' ORDER BY ' + sort
        else:
            query += ' ORDER BY effname ASC'

        query += ' LIMIT %s'
        args.append(self.limit)

        return (query, args)


class Database:
    def __init__(self, dsn, readonly=True):
        self.db = psycopg2.connect(dsn)
        if readonly:
            self.db.set_session(readonly=True, autocommit=True)
        self.cursor = self.db.cursor()

    def CreateSchema(self):
        self.cursor.execute("""
            DROP TABLE IF EXISTS packages CASCADE
        """)

        self.cursor.execute("""
            DROP TABLE IF EXISTS repositories CASCADE
        """)

        self.cursor.execute("""
            CREATE TABLE packages (
                repo varchar(255) not null,
                family varchar(255) not null,

                name varchar(255) not null,
                effname varchar(255) not null,

                version varchar(255) not null,
                origversion varchar(255),
                effversion varchar(255),
                versionclass smallint,

                maintainers varchar(1024)[],
                category varchar(255),
                comment text,
                homepage varchar(1024),
                licenses varchar(1024)[],
                downloads varchar(1024)[],

                ignorepackage bool not null,
                shadow bool not null,
                ignoreversion bool not null
            )
        """)

        self.cursor.execute("""
            CREATE INDEX ON packages(effname)
        """)

        # repositories
        self.cursor.execute("""
            CREATE TABLE repositories (
                name varchar(255) not null primary key,

                num_packages integer,
                num_packages_newest integer,
                num_packages_outdated integer,
                num_packages_ignored integer,

                last_update timestamp with time zone
            )
        """)

        # repo_metapackages
        self.cursor.execute("""
            CREATE MATERIALIZED VIEW repo_metapackages
                AS
                    SELECT
                        repo,
                        effname,
                        count(nullif(versionclass=1, false)) AS num_newest,
                        count(nullif(versionclass=2, false)) AS num_outdated,
                        count(nullif(versionclass=3, false)) AS num_ignored
                    FROM packages
                    WHERE effname IN (
                        SELECT
                            effname
                        FROM packages
                        GROUP BY effname
                        HAVING count(nullif(shadow, true)) > 0
                    )
                    GROUP BY effname,repo
                WITH DATA
        """)

        self.cursor.execute("""
            CREATE UNIQUE INDEX ON repo_metapackages(repo, effname)
        """)

        self.cursor.execute("""
            CREATE INDEX ON repo_metapackages(effname)
        """)

        # maintainer_metapackages
        self.cursor.execute("""
            CREATE MATERIALIZED VIEW maintainer_metapackages
                AS
                    SELECT
                        unnest(maintainers) as maintainer,
                        effname,
                        count(1) AS num_packages,
                        count(nullif(versionclass = 1, false)) AS num_packages_newest,
                        count(nullif(versionclass = 2, false)) AS num_packages_outdated,
                        count(nullif(versionclass = 3, false)) AS num_packages_ignored
                    FROM packages
                    GROUP BY maintainer, effname
                WITH DATA
        """)

        self.cursor.execute("""
            CREATE UNIQUE INDEX ON maintainer_metapackages(maintainer, effname)
        """)

        # maintainers
        self.cursor.execute("""
            CREATE MATERIALIZED VIEW maintainers AS
                SELECT
                    unnest(maintainers) AS maintainer,
                    count(1) AS num_packages,
                    count(DISTINCT effname) AS num_metapackages,
                    count(nullif(versionclass = 1, false)) AS num_packages_newest,
                    count(nullif(versionclass = 2, false)) AS num_packages_outdated,
                    count(nullif(versionclass = 3, false)) AS num_packages_ignored
                FROM packages
                GROUP BY maintainer
                ORDER BY maintainer
            WITH DATA
        """)

        self.cursor.execute("""
            CREATE UNIQUE INDEX ON maintainers(maintainer)
        """)

        # repo counts
        self.cursor.execute("""
            CREATE MATERIALIZED VIEW metapackage_repocounts AS
                SELECT
                    effname,
                    count(DISTINCT repo) AS num_repos,
                    count(DISTINCT family) AS num_families
                FROM packages
                GROUP BY effname
                ORDER BY effname
            WITH DATA
        """)

        self.cursor.execute("""
            CREATE UNIQUE INDEX ON metapackage_repocounts(effname)
        """)

        self.cursor.execute("""
            CREATE INDEX ON metapackage_repocounts(num_repos)
        """)

        self.cursor.execute("""
            CREATE INDEX ON metapackage_repocounts(num_families)
        """)

    def Clear(self):
        self.cursor.execute("""DELETE FROM packages""")
        self.cursor.execute("""
            UPDATE repositories
            SET
                num_packages = 0,
                num_packages_newest = 0,
                num_packages_outdated = 0,
                num_packages_ignored = 0
        """)

    def AddPackages(self, packages):
        self.cursor.executemany("""INSERT INTO packages(
            repo,
            family,

            name,
            effname,

            version,
            origversion,
            effversion,
            versionclass,

            maintainers,
            category,
            comment,
            homepage,
            licenses,
            downloads,

            ignorepackage,
            shadow,
            ignoreversion
        ) VALUES (
            %s,
            %s,

            %s,
            %s,

            %s,
            %s,
            %s,
            %s,

            %s,
            %s,
            %s,
            %s,
            %s,
            %s,

            %s,
            %s,
            %s
        )""",
            [
                (
                    package.repo,
                    package.family,

                    package.name,
                    package.effname,

                    package.version,
                    package.origversion,
                    package.effversion,
                    package.versionclass,

                    package.maintainers,
                    package.category,
                    package.comment,
                    package.homepage,
                    package.licenses,
                    package.downloads,

                    package.ignore,
                    package.shadow,
                    package.ignoreversion,
                ) for package in packages
            ]
        )

    def MarkRepositoriesUpdated(self, reponames):
        self.cursor.executemany("""
            INSERT
                INTO repositories (
                    name,
                    last_update
                ) VALUES (
                    %s,
                    now()
                )
                ON CONFLICT (name)
                DO UPDATE SET
                    last_update = now()
        """,
            [ [ name ] for name in reponames ]
        )

    def UpdateViews(self):
        self.cursor.execute("""REFRESH MATERIALIZED VIEW CONCURRENTLY repo_metapackages""");
        self.cursor.execute("""REFRESH MATERIALIZED VIEW CONCURRENTLY maintainer_metapackages""");
        self.cursor.execute("""REFRESH MATERIALIZED VIEW CONCURRENTLY maintainers""");
        self.cursor.execute("""REFRESH MATERIALIZED VIEW CONCURRENTLY metapackage_repocounts""");
        self.cursor.execute("""
            INSERT
                INTO repositories (
                    name,
                    num_packages,
                    num_packages_newest,
                    num_packages_outdated,
                    num_packages_ignored
                ) SELECT
                    repo,
                    count(*),
                    count(nullif(versionclass=1, false)),
                    count(nullif(versionclass=2, false)),
                    count(nullif(versionclass=3, false))
                FROM packages GROUP BY repo
                ON CONFLICT (name)
                DO UPDATE SET
                    num_packages = EXCLUDED.num_packages,
                    num_packages_newest = EXCLUDED.num_packages_newest,
                    num_packages_outdated = EXCLUDED.num_packages_outdated,
                    num_packages_ignored = EXCLUDED.num_packages_ignored
        """)

    def Commit(self):
        self.db.commit()

    def GetMetapackage(self, name):
        self.cursor.execute("""
            SELECT
                repo,
                family,

                name,
                effname,

                version,
                origversion,
                effversion,
                versionclass,

                maintainers,
                category,
                comment,
                homepage,
                licenses,
                downloads,

                ignorepackage,
                shadow,
                ignoreversion
            FROM packages
            WHERE effname = %s
        """,
            (name,)
        )

        return [
            Package(
                repo=row[0],
                family=row[1],

                name=row[2],
                effname=row[3],

                version=row[4],
                origversion=row[5],
                effversion=row[6],
                versionclass=row[7],

                maintainers=row[8],
                category=row[9],
                comment=row[10],
                homepage=row[11],
                licenses=row[12],
                downloads=row[13],

                ignore=row[14],
                shadow=row[15],
                ignoreversion=row[16],
            ) for row in self.cursor.fetchall()
        ]

    def GetMetapackages(self, *filters, limit=500):
        query, args = MetapackageQueryConstructor(*filters, limit=limit).GetQuery()

        self.cursor.execute("""
            SELECT
                repo,
                family,

                name,
                effname,

                version,
                origversion,
                effversion,
                versionclass,

                maintainers,
                category,
                comment,
                homepage,
                licenses,
                downloads,

                ignorepackage,
                shadow,
                ignoreversion
            FROM packages WHERE effname IN (
                {}
            ) ORDER BY effname
        """.format(query),
            args
        )

        return [
            Package(
                repo=row[0],
                family=row[1],

                name=row[2],
                effname=row[3],

                version=row[4],
                origversion=row[5],
                effversion=row[6],
                versionclass=row[7],

                maintainers=row[8],
                category=row[9],
                comment=row[10],
                homepage=row[11],
                licenses=row[12],
                downloads=row[13],

                ignore=row[14],
                shadow=row[15],
                ignoreversion=row[16],
            ) for row in self.cursor.fetchall()
        ]

    def GetPackagesCount(self):
        self.cursor.execute("""SELECT count(*) FROM packages""")

        return self.cursor.fetchall()[0][0]

    def GetMetapackagesCount(self):
        self.cursor.execute("""SELECT count(*) FROM metapackage_repocounts""")

        return self.cursor.fetchall()[0][0]

    def GetMaintainersCount(self):
        self.cursor.execute("""SELECT count(*) FROM maintainers""")

        return self.cursor.fetchall()[0][0]

    def GetMaintainers(self, offset=0, limit=500):
        self.cursor.execute("""
            SELECT
                maintainer,
                num_packages,
                num_metapackages
            FROM maintainers
            ORDER BY maintainer
            LIMIT %s
            OFFSET %s
        """,
            (limit, offset,)
        )

        return [
            {
                'maintainer': row[0],
                'num_packages': row[1],
                'num_metapackages': row[2]
            } for row in self.cursor.fetchall()
        ]

    def GetRepositories(self):
        self.cursor.execute("""
            SELECT
                name,
                num_packages,
                num_packages_newest,
                num_packages_outdated,
                num_packages_ignored,
                last_update
            FROM repositories
        """)

        return {
            row[0]: {
                'num_packages': row[1],
                'num_packages_newest': row[2],
                'num_packages_outdated': row[3],
                'num_packages_ignored': row[4],
                'last_update': row[5]
            } for row in self.cursor.fetchall()
        }