## alita-graphql

alita-graphql is graphql extension for Alita。

## Installing
```
pip install alita-graphql
```

## Quick Start

```
from alita import Alita
from alita_graphql import GraphQL

class Query(graphene.ObjectType):
    hello = graphene.String(description='A typical hello world')

    def resolve_hello(self, info):
        return 'World'


schema = graphene.Schema(query=Query)

app = Alita('dw')
GraphQL(schema).init_app(app)

```

## Links

- Code: https://github.com/dwpy/alita-graphql