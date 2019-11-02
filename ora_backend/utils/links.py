from urllib.parse import urlencode, urlparse, parse_qs


def generate_pagination_links(
    url, data_list, *, field="after_id", index=-1, exclude=None
):
    if not data_list:
        return {}
    url_components = urlparse(url)
    original_params = parse_qs(url_components.query)

    merged_params = {**original_params, field: data_list[index]["id"]}
    if exclude:
        for key in list(merged_params.keys()):
            if key in exclude:
                merged_params.pop(key, None)
    updated_query = urlencode(merged_params, doseq=True)
    return {"next": url_components._replace(query=updated_query).geturl()}


def generate_next_page_link(url, cur_page=0):
    url_components = urlparse(url)
    original_params = parse_qs(url_components.query)

    merged_params = {**original_params, "page": cur_page + 1}
    updated_query = urlencode(merged_params, doseq=True)
    return url_components._replace(query=updated_query).geturl()
