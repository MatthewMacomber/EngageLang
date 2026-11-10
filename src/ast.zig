pub const PropInit = struct {
    name: []const u8,
    value: *const Expr,
};

pub const Expr = union(enum) {
    number: f64,
    string: []const u8,
    ident: []const u8,
    self_expr,
    none_expr,
    vector_lit,
    table_lit,
    result_lit: struct {
        is_ok: bool,
        value: ?*const Expr,
    },
    new_instance: struct {
        record_name: []const u8,
        props: []const PropInit,
    },
    member_access: struct {
        object: *const Expr,
        member: []const u8,
    },
    index_access: struct {
        object: *const Expr,
        index: *const Expr,
    },
    unary_op: struct {
        op: []const u8,
        operand: *const Expr,
    },
    bin_op: struct {
        op: []const u8,
        left: *const Expr,
        right: ?*const Expr,
    },
    func_call: struct {
        callee: *const Expr,
        args: []const *const Expr,
    },
    receive_expr: struct {
        channel: *const Expr,
    },
};

pub const IfBranch = struct {
    condition: *const Expr,
    body: []const Stmt,
};

pub const PropertyDef = struct {
    name: []const u8,
    default_value: ?*const Expr,
};

pub const FuncDef = struct {
    name: []const u8,
    params: []const []const u8,
    body: []const Stmt,
};

pub const RecordDef = struct {
    name: []const u8,
    properties: []const PropertyDef,
    methods: []const FuncDef,
};

pub const FiberDef = struct {
    name: []const u8,
    body: []const Stmt,
};

pub const FfiType = enum {
    auto,
    number,
    int,
    string,
    bool_type,
    pointer,
    void_type,
};

pub const ExternParam = struct {
    name: []const u8,
    ffi_type: FfiType = .auto,
};

pub const ImportSymbol = struct {
    name: []const u8,
    alias: ?[]const u8 = null,
    params: ?[]const ExternParam = null,
    ret_type: FfiType = .auto,
};

pub const ExternFnDef = struct {
    library: []const u8,
    name: []const u8,
    alias: ?[]const u8 = null,
    params: []const ExternParam = &.{},
    ret_type: FfiType = .auto,
    has_explicit_sig: bool = false,
};

pub const Stmt = union(enum) {
    var_assign: struct {
        name: []const u8,
        value: *const Expr,
    },
    set_stmt: struct {
        target: *const Expr,
        value: *const Expr,
    },
    index_assign: struct {
        object: *const Expr,
        index: *const Expr,
        value: *const Expr,
    },
    func_def: FuncDef,
    record_def: RecordDef,
    if_stmt: struct {
        branches: []const IfBranch,
        else_body: []const Stmt,
    },
    while_stmt: struct {
        condition: *const Expr,
        body: []const Stmt,
    },
    repeat_stmt: struct {
        count: *const Expr,
        body: []const Stmt,
    },
    for_each_stmt: struct {
        item_name: []const u8,
        iterable: *const Expr,
        body: []const Stmt,
    },
    return_stmt: struct {
        value: ?*const Expr,
    },
    break_stmt,
    continue_stmt,
    channel_decl: struct {
        name: []const u8,
    },
    send_stmt: struct {
        value: *const Expr,
        channel: *const Expr,
    },
    fiber_def: FiberDef,
    yield_stmt: struct {
        value: ?*const Expr,
    },
    task_stmt: struct {
        body: []const Stmt,
    },
    import_stmt: struct {
        module_path: []const u8,
        alias: ?[]const u8,
    },
    from_import_stmt: struct {
        module_path: []const u8,
        symbols: []const ImportSymbol,
    },
    extern_fn_def: ExternFnDef,
    expr_stmt: *const Expr,
};

pub const Program = struct {
    statements: []const Stmt,
};
