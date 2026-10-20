-- Esquema mínimo del e-commerce. Lo ejecuta la imagen oficial al inicializar.
create table products (
    id          serial primary key,
    name        text    not null,
    price_cents integer not null check (price_cents >= 0),
    stock       integer not null check (stock >= 0)
);

create table orders (
    id          serial primary key,
    total_cents integer     not null,
    created_at  timestamptz not null default now()
);

create table order_items (
    order_id        integer not null references orders (id),
    product_id      integer not null references products (id),
    qty             integer not null check (qty > 0),
    unit_price_cents integer not null,
    primary key (order_id, product_id)
);

insert into products (name, price_cents, stock) values
    ('Teclado mecánico', 59990, 10),
    ('Mouse inalámbrico', 24990, 25),
    ('Monitor 27"', 199990, 5),
    ('Audífonos', 39990, 15),
    ('Webcam 1080p', 29990, 8),
    ('Hub USB-C', 19990, 30);
