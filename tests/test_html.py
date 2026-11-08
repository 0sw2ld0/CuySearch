from cuysearch.html import analizar


def test_tolera_etiquetas_sin_cerrar_y_cierres_sobrantes():
    arbol = analizar("<ul><li>uno<li>dos</b></ul><p>tres<p>cuatro")

    assert [li.texto() for li in arbol.buscar("li")] == ["uno", "dos"]
    assert [p.texto() for p in arbol.buscar("p")] == ["tres", "cuatro"]


def test_ignora_scripts_y_conserva_espacios_entre_etiquetas():
    arbol = analizar("<div class='a b'><script>x()</script><b>hola</b> <i>mundo</i></div>")

    assert arbol.primero("div", "b").texto() == "hola mundo"


def test_busca_por_clase_parcial_y_atributo_con_guion():
    arbol = analizar('<div data-type="web"><div class="snippet-title x">T</div></div>')

    web = arbol.primero("div", data_type="web")
    assert web is not None
    assert web.primero("div", clase_parcial="title").texto() == "T"
