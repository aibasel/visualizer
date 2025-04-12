from experiment_data import ExperimentData

def translate(config):
    if config["version"] == "1.0":
        return translate_from_1dot0(config)
    else:
        return config


def translate_from_1dot0(config):
    assert(config["version"] == "1.0")


    exp_data = ExperimentData()
    exp_data.properties_url = config["properties_file"]

    new_report_type = ""
    new_report_config = {}
    match config["reportType"]:
        case 0: # old absolute
            new_report_type = 0
            new_report_config = translate_from_1dot0_absolute(config)
        case 1: # old diff
            new_report_type = 3
            new_report_config = translate_from_1dot0_diff(config)
        case 2: # old problem
            new_report_type = 4
            new_report_config = translate_from_1dot0_problem(config, exp_data)
        case 3: # old scatter
            new_report_type = 5
            new_report_config = translate_from_1dot0_scatter(config, exp_data)
        case 4: # old wise (now attribute)
            new_report_type = 1
            new_report_config = translate_from_1dot0_attribute(config, exp_data)
        case _:
            print("ERROR") # TODO


    new_config = {
        "repn" : new_report_type,
        "data": {
            "url" : config["properties_file"]
        },
        "rep" : new_report_config
    }
    if "custom_min_wins" in config:
        new_config["data"]["minw"] = {exp_data.get_numeric_attribute_position(attr): val for attr, val in config["custom_min_wins"].items()}
    if "custom_aggregators" in config:
        new_config["data"]["aggs"] =  {exp_data.get_numeric_attribute_position(attr): val for attr, val in config["custom_aggregators"].items()}

    return new_config


def translate_from_1dot0_absolute(config):
    d = dict()
    if "algorithms" in config:
        d["algs"] = config["algorithms"]
    if "attributes" in config:
        d["attrs"] = config["attributes"]
    if "domains" in config:
        d["doms"] = config[ "domains"]
    if "precision" in config:
        d["prec"] = config["precision"]
    return d


def translate_from_1dot0_attribute(config, exp_data):
    d = dict()
    if "attribute" in config and config["attribute"] != "--":
        d["attr"] = exp_data.get_numeric_attribute_position(config["attribute"])
    return d


def translate_from_1dot0_diff(config):
    d = dict()
    if config.get("algorithm1", "--") != "--" and config.get("algorithm2", "--") != "--":
        d["aps"] = [[config["algorithm1"], config["algorithm2"]]]
    if "percentual" in config:
        d["rel"] = config["percentual"]
    if "attributes" in config:
        d["attrs"] = config["attributes"]
    if "domains" in config:
        d["doms"] = config[ "domains"]
    if "precision" in config:
        d["prec"] = config["precision"]
    return d


def translate_from_1dot0_problem(config, exp_data):
    d = dict()
    if config.get("domain", "--") != "--":
        d["dom"] = config["domain"]
    if config.get("problem", "--") != "--":
        d["prob"] = config["problem"]
    if "algorithms" in config:
        d["algs"] = [exp_data.algorithms[alg].id for alg in config["algorithms"]]
    return d


def translate_from_1dot0_scatter(config, exp_data):
    d = dict()
    if "entries_list" in config:
        aps_config = []
        lines = config["entries_list"].split("\n")
        for line in lines:
            tokens = [x for x in line.split(" ") if x != ""]
            if len(tokens) == 1:
                tokens.append(tokens[0])
            aps_config.append((tokens[0], tokens[1]))
        d["aps"] = aps_config
    if "xattribute" in config:
        d["xattr"] = exp_data.get_numeric_attribute_position(config["xattribute"])
    if "yattribute" in config:
        d["yattr"] = exp_data.get_numeric_attribute_position(config["yattribute"])
    if "xscale" in config:
        d["xsc"] = config["xscale"]
    if "yscale" in config:
        d["ysc"] = config["yscale"]
    if "relative" in config:
        d["rel"] = config["relative"]
    if "groupby" in config:
        d["grp"] = config["groupby"]
    if "replace_zero" in config:
        d["rep0"] = config["replace_zero"]
    if "marker_size" in config:
        d["m_si"] = config["marker_size"]
    if "marker_fill_alpha" in config:
        d["m_al"] = config["marker_fill_alpha"]
    if "colors" in config:
        d["clrs"] = config["colors"]
    if "markers" in config:
        d["mrks"] = config["markers"]
    return d


# 'colors': ['black', 'red', 'teal', 'orange', 'purple', 'olive', 'lime', 'cyan'],
# 'markers': ['x', 'circle', 'triangle', 'asterisk', 'diamond', 'cross', 'star', 'inverted_triangle', 'plus', 'hex', 'y', 'circle_cross', 'square_cross', 'diamond_cross', 'circle_x', 'square_x', 'square_pin', 'triangle_pin'],