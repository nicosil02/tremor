# Literatura sobre determinantes de conflictos en territorios extractivos

Revisión para diseñar las variables del modelo distrito × mes de Tremor (Perú).
Fecha de la revisión: 2026-11-07.

## Cómo leer este documento

- **[VERIFICADO]**: dato leído en el texto completo (PDF) de la versión indicada.
- **[NO VERIFICADO]**: dato tomado del resumen del editor o de cómo lo describen otros autores, porque no se pudo abrir el texto completo. No usar estas cifras como si fueran del paper.
- Todas las cifras vienen de las tablas o del texto de los PDFs. Si un número no aparece, es porque no estaba disponible y no se reconstruyó.

### Qué se pudo leer y qué no

| # | Estudio | Acceso al texto completo | Versión leída |
|---|---|---|---|
| 1 | Castellares y Fouché (2017) | Sí | DT BCRP 2017-005, PDF completo (28 pp.) |
| 2 | Ponce y McClintock (2014) | **No** (muro de pago de Cambridge, 30 USD) | Solo el resumen del editor y lo que reporta CIES (2019) |
| 3 | Haslam y Tanimoune (2016) | **No** (ScienceDirect pide CAPTCHA; no hay preprint abierto) | Solo el resumen y lo que reportan Castellares y Fouché (2017) y CIES (2019) |
| 4 | Christensen (2019) | Sí, versión de trabajo | "Concession Stands", borrador del 19 feb. 2018 (copia en EITI). No es la versión publicada en IO 2019 |
| 5 | Arce (2014), libro | **No** (Project MUSE, sin acceso abierto) | Se leyó Arce (2008/2011), que es cualitativo. Los resultados del libro vienen solo de reseñas |
| 6 | Arellano-Yanguas (2011), JDS | **No** (Taylor & Francis pide verificación de bot) | Se leyó el IDS Working Paper 300 (2008), que es cualitativo, y el resumen de RePEc |
| 7 | Berman, Couttenier, Rohner y Thoenig (2017) | Sí, versión de trabajo | OxCarre RP 141 / CEPR DP 10089 (2014). No es el texto publicado en la AER |
| 8a | Sexton (2018/2020) | Sí, versión de trabajo | ESOC WP 9 (abril 2018). La versión publicada en JCR 2020 está tras muro de pago |
| 8b | Archer Pérez y Barrantes (2019), CIES | Sí | Informe final completo (61 pp.) |
| 8c | Maldonado (2015), tesis Berkeley, cap. 1 | Sí (solo la sección de conflicto electoral) | Tesis completa en eScholarship |
| 8d | Orihuela, Pérez y Huaroto (2019), EXIS | **No** | Solo lo que reporta CIES (2019) |

---

## 1. Castellares y Fouché (2017), BCRP [VERIFICADO]

**Cita.** Castellares, R. y Fouché, M. (2017). *Determinantes de los Conflictos Sociales en Zonas de Producción Minera*. Documento de Trabajo N.° 2017-005, Banco Central de Reserva del Perú, junio de 2017. El PDF está en español, aunque el título en inglés es "Determinants of Social Conflicts in Mining Sites".

- **Unidad, periodo y país.** Pares distrito × empresa minera × año, en Perú, entre 2008 y 2015. La muestra incluye el distrito productor y otros distritos de la misma provincia cuya capital está a menos de 50, 75 o 100 km. Según la especificación hay entre 8,153 y 10,723 observaciones.
- **Fuente de conflictos.** Los reportes mensuales de conflictos sociales de la Defensoría del Pueblo, cruzados con la producción minera por distrito, empresa y mineral del MINEM. Solo se usan conflictos socioambientales vinculados a la minería. Para 2014 había 70 distritos con al menos un conflicto medioambiental y 146 con producción minera.
- **Variable dependiente.** Vale 1 si en el distrito d de la provincia p hay un conflicto con la minera m en el año t. Aunque los reportes de la Defensoría son mensuales, el modelo es anual.
- **Método.** Modelo lineal de probabilidad. Los autores no usan logit ni probit porque hay muchos efectos fijos. Incluye efectos fijos de distrito, de empresa, de distrito × empresa, de año y de tipo de metal, con errores robustos. Como la mayoría de las variables son invariantes en el tiempo, se identifican por su interacción con la dummy "Local", que vale 1 si la mina opera en el mismo distrito.
- **Resultados (interacciones con Local), Tabla 2, columnas 4 a 6 (75 km):**
  - Pobreza 2007: +0.230\*\*\* (sin efectos fijos de distrito) y +0.067\*\*\* / +0.074\*\*\* (con efectos fijos). En la muestra de 50 km con efectos fijos no es significativa (0.024 y 0.031).
  - Gini 2007: entre +0.75 y +0.96, con \*\*\* en todas las especificaciones.
  - Empresa extranjera: entre +0.042\*\*\* y +0.098\*\*\*.
  - Índice de precios de los metales extraídos (log): entre +0.020\* y +0.052\*\*\*. El término directo es negativo y no significativo (entre −0.009 y −0.025).
  - Sanciones acumuladas de OEFA a la empresa (log, rezagadas, a nivel provincial): +0.032\*\*\*.
  - Altitud (log): entre +0.016 y +0.017\*\*\*.
  - Participación de pequeños agricultores (parcelas de menos de 5 ha): +0.128\*\*\* con efectos fijos. No es significativa sin ellos ni en la prueba de robustez con distritos vecinos (Tabla 3).
  - Proporción del gasto municipal en medio ambiente (MEF): entre −0.18\*\* y −0.40\*\*\*.
  - Voto 2006 por partidos regionales antimineros: entre +0.07 y +0.14 (\*\* o \*\*\*).
  - Conflictos sociales no mineros acumulados per cápita: entre +0.18 y +0.45\*\*\*.
- **Efectos marginales (Tabla 4, comparando los percentiles 75 y 25 y los percentiles 90 y 10):**
  - Empresa extranjera: +4 pp en el estimado base y +10 pp en el alternativo.
  - Gini: +4 pp (p75−p25) y +10 pp (p90−p10).
  - Pobreza: +3 pp y +5 pp.
  - Pequeños agricultores: +4 pp y +8 pp.
  - Altitud: +2 pp y +5 pp.
  - Sanciones: +2 pp.
  - Voto antiminero: +2 pp y +4 pp.
  - Gasto ambiental: −2 pp y −5 pp.
  - Conflictos no mineros acumulados: +5 pp (p90−p10).
- **Resultado nulo clave.** El efecto total del precio de los metales es positivo pero **no significativo** en los distritos productores: +0.02 y +0.03 sin estrellas en la Tabla 4. En los distritos vecinos, una subida de precios **reduce** la probabilidad de conflicto. La población tampoco es significativa.
- **Lo que implica para Tremor.** Hay pocas variables que cambian rápido. Los mismos autores dicen que la pobreza, el Gini y la altitud no explican la aparición repentina de conflictos, y apuntan al incumplimiento de compromisos y, en menor medida, a los precios. Variables a usar:
  - Estructurales: pobreza y Gini del mapa de pobreza INEI, altitud, voto antiminero del JNE/INFOGOB, empresa extranjera del MINEM.
  - Dinámicas: sanciones de OEFA acumuladas y rezagadas, historia de conflictos no mineros (Defensoría y EGPP) y la ejecución del gasto ambiental (MEF Consulta Amigable).

## 2. Ponce y McClintock (2014), LAPS [NO VERIFICADO: sin texto completo]

**Cita.** Ponce, A. F. y McClintock, C. (2014). "The Explosive Combination of Inefficient Local Bureaucracies and Mining Production: Evidence from Localized Societal Protests in Peru". *Latin American Politics and Society* 56(3): 118-140. doi:10.1111/j.1548-2456.2014.00243.x. Cambridge lo publicó en línea el 2 de enero de 2018, de ahí la confusión con el año. El volumen y las páginas son de 2014.

- **Lo que dice el resumen del editor (leído).** Usa datos subnacionales del Perú para 2004-2009 y la encuesta LAPOP 2010. Confirma que el conflicto lo provocan tanto las externalidades negativas de la minería como los ingresos del canon. La capacidad burocrática local es una variable independiente significativa: más capacidad atenúa los efectos de la "maldición de los recursos" local.
- **Lo que reporta CIES (2019, p. 8), de segunda mano:** el análisis es regional. Los conflictos socioambientales:
  - **bajan** cuando sube la proporción ejecutada del canon (la proxy de capacidad burocrática) y cuando sube el PIB per cápita;
  - **suben** con el canon per cápita, los conflictos del año previo, la producción minera per cápita, la proporción de contribuyentes y que la autoridad local sea de oposición al gobierno nacional.
- **No verificado.** La unidad exacta (región, provincia o distrito), la fuente de conflictos (probablemente la Defensoría, sin confirmar), el método, los coeficientes y las magnitudes.
- **Lo que implica para Tremor.** El canon per cápita debe ir junto con la tasa de ejecución presupuestal municipal (avance de ejecución del canon o de inversión en MEF Consulta Amigable, con datos mensuales) y su interacción. También conviene incluir los conflictos del periodo anterior, la producción minera per cápita (MINEM o BCRP) y el alineamiento partidario entre alcalde y gobierno (JNE).

## 3. Haslam y Tanimoune (2016), World Development [NO VERIFICADO: sin texto completo]

**Cita.** Haslam, P. A. y Tanimoune, N. A. (2016). "The Determinants of Social Conflict in the Latin American Mining Sector: New Evidence with Quantitative Data". *World Development* 78: 401-419. doi:10.1016/j.worlddev.2015.10.020.

- **Del resumen y registros bibliográficos.** Son 640 propiedades mineras geolocalizadas, en etapa de exploración avanzada o posterior. Prueban tres grupos de hipótesis: las de la firma, las de medios de vida y las socioeconómicas. Una charla de 2013 sobre una versión previa, con 783 propiedades, dijo que las dos primeras hipótesis tenían fuerte respaldo y que había "poco apoyo" para vincular la pobreza con el conflicto.
- **Lo que reportan otros, sin verificar:**
  - Castellares y Fouché (2017): 783 propiedades en 23 países (parece la versión previa). Encuentran más conflicto con mayor pobreza, cercanía a un área protegida, escasez de tierra agrícola y proporción indígena. Los hogares con piso de cerámica tienen menos conflicto. Las empresas en conflicto eran extranjeras en 62.41 % de los casos, frente a 58.38 % de las que no estaban en conflicto. La minería subterránea tiene menos conflicto que la de tajo abierto. También usan la altitud.
  - CIES (2019): son cinco países (Argentina, Brasil, Chile, México y Perú). Importan la pobreza en interacción con la falta de servicios del Estado, la escasez de tierras agrícolas, el tajo abierto, la altitud, la propiedad extranjera, las firmas grandes o medianas y la proporción de PEA.
- **Contradicciones de segunda mano.** No coinciden el número de países (23 o 5), el número de propiedades (783 o 640) ni el papel de la pobreza. Antes de citar cifras de este estudio hay que conseguir el PDF.
- **No verificado.** La variable dependiente exacta, el método (se presume logit, sin confirmar), los coeficientes y el periodo.
- **Lo que implica para Tremor.** Tipo de mina (tajo abierto o subterránea) y tamaño, del MINEM o del catastro de Ingemmet, cercanía a un ANP (SERNANP), presión sobre la tierra agrícola (CENAGRO 2012), proporción indígena o de comunidades campesinas (Censo 2017 y BDPI del Ministerio de Cultura) y propiedad extranjera.

## 4. Christensen (2019), International Organization [VERIFICADO en la versión de trabajo de feb. 2018]

**Cita.** Christensen, D. (2019). "Concession Stands: How Mining Investments Incite Protest in Africa". *International Organization* 73(1): 65-101. Se leyó el borrador del 19 de febrero de 2018, alojado por EITI. La versión ESOC WP 6 y la de eScholarship no se pudieron descargar (acceso denegado). Las cifras pueden diferir un poco de la versión publicada.

- **Unidad, periodo y país.** Celdas de 5 × 5 km por año en África, entre 1997 y 2013/14. La muestra completa tiene unos 27 millones de observaciones.
- **Fuentes.** Las minas comerciales y su año de inicio vienen de IntierraRMG, SNL Metals & Mining y Mining eTrack. La protesta viene de ACLED, que es la principal, y los resultados se replican con SCAD, GDELT e ICEWS.
- **Variable dependiente.** Vale 1 si hubo una protesta o un disturbio en la celda ese año.
- **Método.** Diferencias en diferencias con modelo lineal de probabilidad y efectos fijos de celda y año (en algunas especificaciones, de país × año y de área × año). Los errores se agrupan por celda.
- **Resultados principales:**
  - El **inicio de la producción** de una mina hace que la probabilidad de protesta o disturbio **más que se duplique** respecto al nivel previo en la misma celda. En la Tabla 1, el coeficiente de D_it es de alrededor de 0.01\* con una media de 0.0003 a 0.0035 según la muestra.
  - El efecto **decae con la distancia**: a partir de unos 10 km del área minera se acerca a cero.
  - No hay efecto anticipado en exploración ni construcción: los placebos, que abarcan los 5 años previos, son nulos.
  - Los **precios mundiales** (log) suben la protesta: entre +0.008† y +0.018\* en la Tabla 2. Una subida de alrededor de 1 punto log, como la del oro entre 1997 y 2007, más o menos duplica la probabilidad media de protesta en celdas mineras.
  - Ser candidato de **EITI** reduce la relación precio-protesta en alrededor de 15 %, y ser país cumplidor la reduce en aproximadamente el doble (Tabla 3). Por ejemplo, la interacción del precio con ser cumplidor es de −0.004\* a −0.005†.
  - La **participación parcial del Estado** en la mina elimina el efecto.
- **Resultados nulos importantes.** No hay efecto sobre la rebelión ni sobre conflictos armados. No hay mayor efecto en minas de tajo abierto, ni cerca de áreas protegidas, ni con estrés hídrico. No influyen la migración (medida con DHS), la desigualdad, la percepción de corrupción ni el que el dueño sea chino o esté en un paraíso fiscal. Tampoco aparece sesgo de cobertura mediática.
- **Lo que implica para Tremor.** La variable más fuerte es el **cambio de estado de la mina** (inicio de producción) en el distrito o a pocos kilómetros, según el MINEM y el catálogo de unidades en producción. Eso apunta a usar un buffer de cercanía (0-10 km) en vez de la frontera distrital, y también precios mundiales ponderados por la canasta minera del distrito (BCRP o Pink Sheet). No parece valer la pena invertir en variables ambientales estáticas (tajo, ANP, estrés hídrico) como moderadores.

## 5. Arce (2014), *Resource Extraction and Protest in Peru* [NO VERIFICADO: libro no accesible]

**Cita.** Arce, M. (2014). *Resource Extraction and Protest in Peru*. Pittsburgh: University of Pittsburgh Press. Hay edición en español: *La extracción de recursos naturales y la protesta social en el Perú*, PUCP, 2015.

- **Leído en texto completo:** Arce, M. (2008). "The Repoliticization of Collective Action after Neoliberalism in Peru". *LAPS* 50(3): 37-62. Se leyó la traducción en *Debates en Sociología* 36 (2011): 57-83.
  - Es un estudio **cualitativo y descriptivo**: casos del Arequipazo y de Cajamarca y Yanacocha, más una serie mensual de protestas entre 1987 y 2006 de la "Base de protestas sociales del Perú" (Arce 2010), que es la base que Tremor llama EGPP.
  - **No tiene regresiones**. Su aporte es mostrar que las protestas están "territorializadas", que los bloqueos de carreteras son un repertorio dominante y que la apertura política (el paso de Fujimori a Toledo) aumenta la movilización.
- **Del libro, solo de segunda mano (reseñas):** la correlación entre la protesta y la **fragmentación política subnacional** (muchos movimientos independientes con poco voto cada uno) es más fuerte que la correlación con las rentas extractivas. Otro trabajo lo resume así: "political fragmentation (indicated by a higher number of parties) increases protest". Usa datos de prensa de 31 años.
- **No verificado.** La unidad (probablemente región-año), el método, los coeficientes y el efecto del canon.
- **Lo que implica para Tremor.** Fragmentación electoral distrital y provincial, medida como número efectivo de listas o porcentaje del voto del ganador (JNE/INFOGOB), y la propia base EGPP como variable dependiente o como rezago. Como la base viene de prensa, hay que tener en cuenta el **sesgo de cobertura**.

## 6. Arellano-Yanguas (2011), Journal of Development Studies [NO VERIFICADO: sin texto completo]

**Cita.** Arellano-Yanguas, J. (2011). "Aggravating the Resource Curse: Decentralisation, Mining and Conflict in Peru". *Journal of Development Studies* 47(4): 617-638. doi:10.1080/00220381003706478.

- **Del resumen (RePEc).** Perú adoptó un enfoque "localista": envió las rentas mineras a los gobiernos subnacionales y pidió a las empresas un papel local más activo. Según la evidencia **estadística y de campo**, eso **agravó** el conflicto local.
- **Lo que reporta CIES (2019), sin verificar:** el canon explica la incidencia de conflictos **a nivel regional entre 2005 y 2008**, y la pobreza y el volumen de la inversión minera la aumentan. Orihuela, Pérez y Huaroto (2019) replicaron el estudio y encontraron que la relación positiva entre canon y conflicto **solo se cumple al inicio de la expansión del canon** y que luego desaparece. Depende de la definición de las variables y del periodo.
- **Leído en texto completo:** el IDS Working Paper 300 (2008), *A Thoroughly Modern Resource Curse?* Es cualitativo, con entrevistas y los casos de Cajamarca y Espinar. Sostiene que la descentralización trasladó la maldición de los recursos al nivel subnacional por:
  - el gasto rápido y atomizado del canon bajo presión;
  - el clientelismo y los fondos privados como el Acuerdo Marco de Tintaya, que compiten con el Estado;
  - la debilidad regulatoria del MEM;
  - la percepción de colusión entre el Estado y las empresas.

  Según el texto, en 2006 los conflictos abiertos pasaron de 6 a 35, y 21 de ellos (60 %) eran mineros, de acuerdo con la Defensoría. **No hay regresiones.**
- **Lo que implica para Tremor.** Canon y regalías por distrito y mes (MEF transferencias), su **volatilidad** y el **cambio** respecto al año anterior, más que el nivel. Conviene interactuarlos con la capacidad de ejecución. Hay que ser escépticos con el efecto del canon en niveles, según Orihuela et al.

## 7. Berman, Couttenier, Rohner y Thoenig (2017), AER [VERIFICADO en la versión de trabajo de 2014]

**Cita.** Berman, N., Couttenier, M., Rohner, D. y Thoenig, M. (2017). "This Mine Is Mine! How Minerals Fuel Conflicts in Africa". *American Economic Review* 107(6): 1564-1610. Se leyó la versión de trabajo OxCarre RP 141 / CEPR DP 10089 (2014). El PDF de la AER en core.ac.uk estaba bloqueado por Cloudflare.

- **Unidad, periodo y país.** Celdas de 0.5° × 0.5° (unos 55 × 55 km) por año en África, entre 1997 y 2010. Son algo más de 10,000 celdas y unas 142,000 observaciones.
- **Fuentes.** Los conflictos vienen de ACLED: batallas, violencia contra civiles y disturbios o protestas. Las minas vienen de Raw Material Data (IntierraRMG): 27 minerales en la versión de trabajo y **14 en la AER**. Los precios vienen del Banco Mundial.
- **Variable dependiente.** La incidencia (al menos un evento en la celda y el año) y el número de eventos.
- **Método.** Modelo lineal de probabilidad con efectos fijos de celda y de país × año. La identificación viene del precio mundial del mineral principal × mina activa, en celdas cuyo estado minero no cambia. Robustez con logit de efectos fijos, PPML y errores de Conley.
- **Resultados principales (versión de trabajo):**
  - Precio (log) × mina: **+0.073\*\*\*** (Tabla 4, columna 2, la especificación preferida).
  - Una desviación estándar más en el precio sube la probabilidad de conflicto de 0.165 a 0.203.
  - La presencia de una mina se asocia con +8.5 pp entre celdas y +4.5 pp dentro de la celda.
  - En las celdas vecinas el efecto es positivo pero menor: +0.024 a +0.028\*\*\* (Tabla 5).
  - **Disturbios y protestas:** incidencia +0.040\*\* y número de eventos +0.079\*\* (Tabla 6). Las batallas también responden: +0.020\*\*\*.
  - La subida de precios aumenta tanto el inicio de los conflictos como su duración.
  - La subida histórica de precios explica hasta **21 %** de la violencia media por país en la versión de trabajo. El resumen de la AER dice "hasta un cuarto", y la cifra es 13.6 % si solo se cuentan los países con más de 50 eventos.
- **Resultados nulos y matices.** Con celdas de 1° × 1° el efecto es más débil. La distancia a la mina reduce el efecto del precio.
- **Solo en la AER, no verificado en el texto:** Christensen (2018) cuenta que Berman et al. encuentran que el efecto de los precios se **atenúa con la participación de empresas públicas domésticas** y apunta en la misma dirección para EITI, pero con muy pocas observaciones porque su muestra termina en 2010.
- **Lo que implica para Tremor.** Un **índice de precios mundiales ponderado por la producción minera del distrito**, con pesos fijos de antes de la muestra para evitar endogeneidad (precios del BCRP y producción del MINEM), un efecto de vecindad espacial (distritos colindantes) y modelos de conteo (PPML o binomial negativa) además de la incidencia.

## 8. Otros estudios cuantitativos peruanos

### 8a. Sexton (2018/2020) [VERIFICADO en la versión ESOC WP 9, abril 2018]

**Cita.** Sexton, R. (2020). "Unpacking the Local Resource Curse: How Externalities and Governance Shape Social Conflict". *Journal of Conflict Resolution* 64(4): 640-673. Se leyó la versión anterior: Sexton, R. (2018), "A New Resource Curse: How Externalities and Governance Shape Social Conflict", ESOC Working Paper 9, Princeton. El PDF se bajó del enlace público en Google Drive de la página de ESOC.

- **Unidad, periodo y país.** Departamento × año en Perú, entre 2007 y 2014: 24 departamentos (Callao va unido a Lima), 192 observaciones.
- **Fuente de conflictos.** 84 reportes mensuales de la **Defensoría del Pueblo** (agosto 2007 a agosto 2014). Dos asistentes los codificaron a mano y además se usaron expresiones regulares, separando tres tipos: "ambiental", "rechazo general" y "demanda de beneficios".
- **Variable dependiente.** El número de incidentes de conflicto minero con mención ambiental, en transformación inversa hiperbólica (asinh), en t+1.
- **Variables y método.** Efectos fijos de departamento y año, con errores agrupados por departamento.
  - El índice de precios estandarizados de 9 commodities (Pink Sheet) se pondera con las minas del departamento en **2001**, un peso previo a la muestra.
  - Los moderadores son la **ejecución presupuestal** del gobierno regional en t−1 y la competitividad electoral (margen menor al 5 %).
- **Resultados principales:**
  - Una desviación estándar más en el precio produce **+20 %** de incidentes ambientales (0.20\*). Los incidentes de rechazo general (0.04) y de demanda de beneficios (0.09) **no son significativos**.
  - El efecto escala con la intensidad minera: −0.01 con 1 mina, 0.32\*\* con 5, 0.48\*\*\* con 10 y 0.64\*\*\* con 20.
  - Los minerales que contaminan de forma aguda (oro, estaño y petróleo) explican el efecto. Con 2 minas: +20 %\*\*\* frente a +6 % no significativo para los que contaminan de forma crónica.
  - La ejecución presupuestal tiene una interacción con el precio de **−2.15** (EE 0.82). Con baja capacidad y baja competencia el efecto llega a **+94 %**, y con alta capacidad y alta competencia es de alrededor de −15 % (no significativo).
  - El canon y las regalías suben 22.7 soles per cápita por desviación estándar, pero **el gasto en las provincias mineras no sube**.
  - Los años electorales **reducen** el efecto del precio: es alrededor de 60 % mayor en los años sin elección.
  - Después de EITI (2010) el efecto del precio **aumenta**: 0.28 frente a 0.11 (Tabla A5).
  - Las empresas **domésticas** explican la mayor parte del efecto.
  - No hay derrames espaciales entre departamentos.
  - Los precios **no** afectan las protestas no mineras de la Defensoría (placebo).
  - Solo los precios ponderados con minas antiguas (anteriores a 2001) explican el conflicto, no los ponderados con minas nuevas.
- **Lo que implica para Tremor.** Es el diseño más parecido a Tremor. Sugiere:
  - un índice de precios por distrito con pesos fijos de producción;
  - una separación entre canasta de contaminación aguda (oro) y crónica (cobre, zinc);
  - la ejecución presupuestal municipal o regional como moderador (MEF);
  - un rezago de alrededor de 12 meses entre el shock de precios y el conflicto, porque el canon de t se transfiere en t+1;
  - el calendario electoral (JNE).

  La unidad departamental tiene poca potencia estadística, así que replicar el diseño a nivel distrital es una contribución en sí misma.

### 8b. Archer Pérez y Barrantes (2019), CIES [VERIFICADO]

**Cita.** Archer Pérez, C. y Barrantes, N. (2019). *"Más allá del canon": entendiendo los determinantes y duración de los conflictos sociales mineros*. Tercer informe final, CIES (PBA1AN59-248), 12/06/2019.

- **Unidad, periodo y país.** Distrito × año en Perú, entre 2006 y 2016: 1,773 distritos y 20,713 observaciones. La duración se estudia por conflicto: 350 episodios activos entre 2005 y 2016.
- **Fuente.** Los Reportes de Conflictos Sociales de la **Defensoría del Pueblo**, digitalizados por los autores. El 95 % de los conflictos socioambientales mineros son distritales.
- **Variables dependientes.** (i) Dummy de al menos un conflicto activo, (ii) número de conflictos distintos y (iii) conflictos ponderados por meses activos. Se estiman para socioambientales y para mineros.
- **Método.** Modelo lineal de probabilidad y modelos lineales de panel con efectos fijos de distrito o con efectos aleatorios con efectos fijos de provincia o región. Todos con efectos fijos de año y errores agrupados por distrito. Robustez con probit de efectos aleatorios. La duración se modela con supervivencia log-logística, reportada como *time ratios*. Los autores advierten que **son correlaciones y no efectos causales**.
- **Resultados para conflicto minero (Tabla 6):**
  - Gran minería (producción por encima del percentil 66): +0.109\* a +0.127\*\*.
  - Mediana y pequeña minería: no significativas.
  - **Canon per cápita (asinh): ≈0.000 a 0.001, no significativo en ninguna especificación.**
  - Pobreza: no significativa en el modelo lineal, pero positiva en el probit (Anexo 1).
  - Percepción de contaminación del agua de riego por relaves (CENAGRO 2012): +0.131\*\*\* / +0.150\*\*\*.
  - Pasivos ambientales mineros por km² (inventario MINEM 2016): +0.425\*\*\* / +0.467\*\*\*.
  - Superficie agropecuaria (asinh): +0.006\*\* / +0.007\*\*.
  - Conflictos socioambientales en la provincia (excluido el distrito): +0.013\*\*\* / +0.014\*\*\*.
  - **Año de elección local: +0.037\*\*\* a +0.042\*\*\*.**
  - Revocatoria o vacancia: −0.017\*\*.
  - Población (asinh): +0.012\*\*\* / +0.014\*\*\*.
  - Altitud: +0.018\*\*\* / +0.019\*\*\*.
- **Resultados nulos.** Canon; tipo de mineral (salvo el oro, que **reduce** el conflicto en el probit); concentración de la tierra; concentración del voto; alcalde reelecto; instrumentos de gestión municipal; participación ciudadana (solo negativa en el probit); variables de género (inconsistentes).
- **Duración.** Los conflictos duran más cuando hay contaminación (TR 1.49), diálogo o mesa (1.85-2.14), organizaciones sociales (1.34-1.39) y violencia, leve o fuerte (1.38-1.43). Duran menos cuando el conflicto abarca más de un distrito geográficamente (0.45-0.51).
- **Lo que implica para Tremor.** Conviene incluir:
  - el **rezago espacial de conflictos en la provincia** (Defensoría y EGPP);
  - un **calendario electoral** con dummy de año o meses previos a elecciones y otra de procesos de revocatoria (JNE);
  - los **pasivos ambientales mineros por km²** (MINEM);
  - la **percepción de contaminación del agua** (CENAGRO);
  - la superficie agropecuaria;
  - la escala de la producción (MINEM y BCRP).

  Si hay mesa de diálogo y violencia previa, el conflicto **persiste**, lo que sirve para modelar la continuidad de un conflicto activo.

### 8c. Maldonado (2015), tesis doctoral, cap. 1 [VERIFICADO en la sección de conflicto electoral]

**Cita.** Maldonado Zambrano, S. H. (2015). *Essays in the Political Economy of Natural Resource Booms*. Tesis doctoral, UC Berkeley. El capítulo 1 es "The Political Effects of Resource Booms...".

- **Unidad y periodo.** Distrito × periodo electoral en Perú, entre 1998 y 2010.
- **Variable dependiente.** Dummy de al menos un incidente de **conflicto electoral** reportado por la ONPE, como destrucción de material o ataque a personal. No es protesta socioambiental.
- **Método.** Diferencias en diferencias y variables instrumentales con transferencias mineras per cápita y su cuadrado.
- **Resultados.** Nivel +0.042\*\* a +0.050\*\*\* y cuadrado −0.002\*\*\* a −0.003\*\*\* (Tabla 1.14). La relación es positiva y no monótona: se invierte solo en los distritos con transferencias extremas. El valor de la producción **no** influye.
- **Lo que implica para Tremor.** Si se usa el canon, debe entrar de forma **no lineal** (asinh, cuadrado o tramos). Los meses electorales pueden traer violencia que la prensa registra como protesta.

### 8d. Orihuela, Pérez y Huaroto (2019) [NO VERIFICADO]

**Cita.** Orihuela, J. C., Pérez, C. A. y Huaroto, C. (2019). "Do Fiscal Windfalls Increase Mining Conflicts? Not Always". *The Extractive Industries and Society* 6(2): 313-318. doi:10.1016/j.exis.2018.07.010.

- **Según CIES (2019) y el resumen de la PUCP:** replican y amplían a Arellano-Yanguas (2011) y encuentran que el efecto del canon sobre el conflicto **depende de la definición de las variables y del periodo**: es positivo al inicio del auge del canon y luego desaparece. No se leyó el texto.

### Sobre bloqueos de vías y el Corredor Minero del Sur

**No se encontró ningún estudio cuantitativo revisado por pares** con datos de distrito o de eventos sobre bloqueos en el Corredor Minero del Sur. Lo disponible son notas de prensa y gremios, como ProActivo, Gestión y Expreso, con cifras incompatibles entre sí: más de 540, 550 o 580 días de bloqueo de Las Bambas entre 2016 y 2022/23. También hay un recuadro del BCRP (Reporte de Inflación, marzo de 2022, recuadro 5) que estima unas 68 mil TMF de cobre no producidas en 2021, pero no se pudo abrir el PDF por el bloqueo antibot del BCRP. Es un vacío que Tremor puede cubrir con las alertas viales de SUTRAN.

---

## Contradicciones entre estudios

1. **¿Importan los precios de los minerales?**
   - **Sí:** Berman et al. (África, versión de trabajo, +0.073\*\*\*), Christensen (África, entre +0.010† y +0.018\*) y Sexton (Perú, departamental, +20 % por desviación estándar, solo en conflictos ambientales y con más fuerza para minerales de contaminación aguda y alta intensidad minera).
   - **No en los distritos productores:** Castellares y Fouché (Perú, distrital). Allí el efecto total no es significativo y en los distritos vecinos es **negativo**.
   - Posibles explicaciones: la variable dependiente (todos los conflictos mineros o solo los ambientales), la unidad (departamento o distrito-empresa), la frecuencia anual y que Castellares y Fouché usan sobre todo variación de corte transversal.
   - Para Tremor esto significa probar el precio separando la canasta aguda (oro) de la crónica, y usar rezagos.
2. **Canon.**
   - **Positivo:** Arellano-Yanguas (2011) y Ponce y McClintock (2014), los dos sin verificar.
   - **Nulo:** CIES (2019) a nivel distrital.
   - **Depende del periodo:** Orihuela et al. (2019).
   - **No monótono:** Maldonado (2015), aunque para conflicto electoral.
   - Sexton muestra que el canon sube con el precio pero el gasto en las zonas mineras no.
   - Conclusión: usar el canon en cambios o en interacción con la ejecución, no solo en niveles.
3. **Empresa extranjera.**
   - Aumenta el conflicto según Castellares y Fouché (+4 a +10 pp) y Haslam y Tanimoune (sin verificar).
   - Según Sexton, las firmas domésticas explican más.
   - Según Christensen, el país de origen (China o paraíso fiscal) no importa, pero la participación del Estado lo elimina.
4. **EITI y transparencia.**
   - Christensen: atenúa el efecto precio-protesta (−15 % como candidato y aproximadamente el doble como cumplidor).
   - Sexton: en Perú, después de EITI el efecto **aumenta**.
5. **Elecciones.**
   - CIES (distrital): un año de elección local **sube** la probabilidad de conflicto minero (+3.7 a +4.2 pp).
   - Sexton (departamental): los años electorales **reducen** el efecto del precio.
   - No es una contradicción directa: uno mide un efecto de nivel y el otro un efecto de interacción.
6. **Pobreza y desigualdad.**
   - Positivas y robustas en Castellares y Fouché.
   - No significativas en el modelo lineal de CIES (positivas solo en el probit).
   - Nulas en Christensen para la desigualdad.
   - "Poco apoyo" para la pobreza en la presentación de 2013 de Haslam y Tanimoune.
7. **Variables ambientales estáticas.**
   - En Perú, los pasivos ambientales y la percepción de contaminación son fuertes (CIES), y el tajo abierto y las ANP aparecen en Haslam y Tanimoune (sin verificar).
   - En África, Christensen no encuentra moderación por tajo, ANP ni estrés hídrico.

---

## Tabla final: variable → evidencia → fuente peruana → prioridad

Prioridad: **alta** si tiene evidencia verificada y consistente, o si es central para la dinámica mensual; **media** si la evidencia es mixta o sin verificar; **baja** si es nula o muy indirecta.

| Variable (distrito × mes) | Evidencia (signo; estudio) | Fuente peruana | Prioridad |
|---|---|---|---|
| Rezago de conflictos y protestas en el propio distrito (t−1…t−12) | + Ponce y McClintock (conflictos del año previo, sin verificar); + Castellares y Fouché (conflictos no mineros acumulados, +5 pp); + Berman (el precio sube el inicio y la duración) | Defensoría (reportes mensuales), EGPP/Arce, prensa | Alta |
| Conflictos en la provincia o en distritos vecinos (rezago espacial) | + CIES (+0.013 a +0.014\*\*\*); + Berman (celdas vecinas); Sexton: sin derrame entre departamentos | Defensoría, EGPP, límites distritales INEI | Alta |
| Producción minera activa y su escala (gran minería) | + CIES (gran minería +0.11 a +0.13); + Berman (+4.5 a +8.5 pp); + Sexton (el efecto escala con el número de minas) | MINEM (producción por unidad y distrito), BCRP (producción nacional) | Alta |
| Inicio de producción de una mina nueva (evento) | + Christensen (la probabilidad más que se duplica; sin efecto en exploración ni construcción) | MINEM (unidades en producción), Ingemmet | Alta |
| Índice de precios mundiales ponderado por la canasta del distrito (pesos fijos previos, rezago de 6 a 12 meses) | + Berman, + Christensen, + Sexton; nulo o negativo en Castellares y Fouché | BCRP (cotizaciones), Banco Mundial Pink Sheet, MINEM (pesos) | Alta (con rezagos) |
| Precio de la canasta de contaminación aguda (oro) frente a la crónica (Cu, Zn, Pb, Ag) | + Sexton (aguda +20 % a +100 % frente a crónica no significativa) | BCRP, MINEM | Media |
| Calendario electoral (año o meses previos a elecciones locales y regionales) y revocatorias | + CIES (+3.7 a +4.2 pp); Sexton: atenúa el efecto precio; Maldonado: conflicto electoral | JNE/INFOGOB, ONPE | Alta |
| Canon y regalías transferidos (cambio y volatilidad, no solo nivel; forma no lineal) | + Arellano-Yanguas y + Ponce (sin verificar); nulo en CIES; depende del periodo en Orihuela; no monótono en Maldonado | MEF (transferencias a gobiernos locales, mensual) | Media |
| Ejecución presupuestal municipal o regional (capacidad burocrática) y su interacción con canon o precio | − Ponce (sin verificar); − Sexton (interacción −2.15); nulo en los instrumentos de gestión municipal de CIES | MEF Consulta Amigable (avance de ejecución mensual) | Alta |
| Pasivos ambientales mineros por km² | + CIES (+0.43 a +0.47\*\*\*; también alargan la duración) | Inventario de PAM, MINEM | Alta (estática) |
| Percepción de contaminación del agua de riego por relaves | + CIES (+0.13 a +0.15\*\*\*) | CENAGRO 2012 (INEI) | Media (estática, de 2012) |
| Sanciones y multas acumuladas de la empresa (rezagadas) | + Castellares y Fouché (+0.032\*\*\*, +2 pp) | OEFA (registro de sanciones e infractores) | Media |
| Pobreza monetaria | + Castellares y Fouché (+3 a +5 pp); nulo en el modelo lineal de CIES y + en su probit; Haslam: "poco apoyo" | Mapa de pobreza INEI 2007, 2013 y 2018; ENAHO (solo a nivel regional) | Media (estática) |
| Desigualdad (Gini distrital) | + Castellares y Fouché (+4 a +10 pp); nulo en Christensen | Mapa de pobreza INEI | Baja |
| Altitud | + Castellares y Fouché (+2 a +5 pp); + CIES (+0.018\*\*\*); + Haslam (sin verificar) | INEI, DEM | Media (control) |
| Población (log o asinh) | + CIES; no significativa en Castellares y Fouché | INEI (censos y proyecciones) | Alta (control o exposición) |
| Superficie agropecuaria y pequeños productores | + CIES (superficie +0.006\*\*); + Castellares y Fouché (parcelas de menos de 5 ha, no robusta) | CENAGRO 2012 | Baja |
| Voto por partidos antimineros o fragmentación política | + Castellares y Fouché (voto antiminero 2006); + Arce 2014 (fragmentación, sin verificar); nulo en la concentración del voto de CIES | JNE/INFOGOB | Media |
| Empresa extranjera o doméstica, participación estatal | + Castellares y Fouché (extranjera); Sexton: domésticas; Christensen: el Estado como socio elimina el efecto | MINEM (titulares), SMV | Baja |
| Gasto municipal en medio ambiente | − Castellares y Fouché (−2 a −5 pp) | MEF Consulta Amigable (función Ambiente) | Baja |
| Cercanía a ANP, tajo abierto, estrés hídrico | + Haslam (sin verificar); nulo en Christensen | SERNANP, MINEM, ANA | Baja |
| Indicadores del propio episodio (diálogo, violencia previa, organizaciones) para la persistencia | + duración en CIES (TR 1.3 a 2.1) | Defensoría (texto de cada caso) | Media (para modelar la persistencia) |
| Bloqueos de vías previos en el distrito o el corredor | Sin estudios cuantitativos; Arce (2008) documenta el bloqueo como repertorio dominante | SUTRAN (alertas viales), Defensoría (acciones colectivas), prensa | Alta (señal operativa nueva, sin respaldo académico) |

## Fuentes consultadas

- Castellares y Fouché (2017): https://www.bcrp.gob.pe/docs/publicaciones/documentos-de-trabajo/dt-2017/dt-2017-005.pdf
- Ponce y McClintock (2014), resumen: https://www.cambridge.org/core/journals/latin-american-politics-and-society/article/explosive-combination-of-inefficient-local-bureaucracies-and-mining-production-evidence-from-localized-societal-protests-in-peru/29AD538D3331AC00CC6071B8FC8E47B2
- Haslam y Tanimoune (2016), registro: https://econpapers.repec.org/RePEc:eee:wdevel:v:78:y:2016:i:c:p:401-419
- Christensen (feb. 2018): https://api.eiti.org/sites/default/files/attachments/concession-stands-feb2018_1.pdf
- Berman et al., OxCarre RP 141: https://ora.ox.ac.uk/objects/uuid:174782c5-0468-43df-9ff4-25147f4d9a82 ; CEPR DP 10089: https://repository.graduateinstitute.ch/record/286975/files/CEPR-Berman2014.pdf
- Arellano-Yanguas, IDS WP 300: https://assets.publishing.service.gov.uk/media/57a08bb040f0b652dd000e22/wp300.pdf ; resumen JDS: https://ideas.repec.org/a/taf/jdevst/v47y2011i4p617-638.html
- Arce (2011, traducción de 2008): https://revistas.pucp.edu.pe/index.php/debatesensociologia/article/download/2171/2102
- Sexton, ESOC WP 9: https://esoc.princeton.edu/publications/esoc-working-paper-9-new-resource-curse-how-externalities-and-governance-shape-social
- Archer Pérez y Barrantes (2019), CIES: https://cies.org.pe/wp-content/uploads/2019/07/if3_perezbarrantes.pdf
- Maldonado (2015): https://escholarship.org/uc/item/53n0046q
- Orihuela et al. (2019), registro: https://cris.pucp.edu.pe/en/publications/do-fiscal-windfalls-increase-mining-conflicts-not-always/
