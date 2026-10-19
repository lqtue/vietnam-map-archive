\ir explore-maps-setup.sql
insert into maps(id,name,year,status,is_georeferenced,regions,region,holding_institution,series_key,map_type,bbox,allmaps_id)
select md5(i::text)::uuid,'Huế Đà Nẵng',1900,'public',true,array['Huế'],'Huế',case when i=1201 then 'Rare institution' else 'BnF' end,'large-series','topographic',array[100,10,110,20]::float8[],'scan' from generate_series(1,1201) i;
insert into maps(id,name,status,is_georeferenced,regions) values
(md5('draft')::uuid,'Private draft','draft',true,array['Secret']),
(md5('archived')::uuid,'Archived','archived',true,array['Secret']),
(md5('pending')::uuid,'Not ready','public',false,array['Secret']),
(md5('undated')::uuid,'Undated','featured',true,array['Huế']);
do $$ declare result jsonb; cursor jsonb; n integer:=0; seen uuid[]:='{}'; row jsonb; begin
 result:=explore_maps_page();
 if (result#>>'{total,maps}')::int<>1202 or jsonb_array_length(result->'maps')<>60 then raise exception 'full count or bounded page failed'; end if;
 if not result#>'{choices,institution}' ? 'Rare institution' then raise exception 'choice beyond 1000 missing'; end if;
 if (result#>>'{facets,institution,BnF}')::int<>1200 then raise exception 'facet incomplete'; end if;
 if result#>'{choices,area}' ? 'Secret' then raise exception 'visibility leaks facet'; end if;
 if (explore_maps_page(p_staff=>null)#>>'{total,maps}')::int<>1202 then raise exception 'null staff gate'; end if;
 if (explore_maps_page(p_filters=>'{"year":["1900","1900"]}')#>>'{total,maps}')::int<>1201 then raise exception 'year excludes undated'; end if;
 if (explore_maps_page(p_filters=>'{"region":["central"]}',p_regions=>'{"central":["Huế"]}')#>>'{total,maps}')::int<>1202 then raise exception 'geographic region filter'; end if;
 if (explore_maps_page(p_staff=>true)#>>'{total,maps}')::int<>1203 then raise exception 'staff draft gate'; end if;
 if (explore_maps_page(p_query=>'hue:* & da:* & nang:*')#>>'{total,maps}')::int<>1201 then raise exception 'accent folding failed'; end if;
 if (explore_maps_page(p_filters=>'{"institution":["Rare institution"]}')#>>'{total,maps}')::int<>1 then raise exception 'institution filter'; end if;
 if (explore_maps_page(p_filters=>'{"institution":["Rare institution"]}')#>>'{facets,institution,BnF}')::int<>1200 then raise exception 'disjunctive facet'; end if;
 if (explore_maps_page(p_point=>'[0,0]')#>>'{total,maps}')::int<>0 then raise exception 'point exclusion'; end if;
 if (explore_maps_page(p_point=>'[105,15]')#>>'{total,maps}')::int<>1201 then raise exception 'point interior inclusion'; end if;
 if (explore_maps_page(p_point=>'[100,10]')#>>'{total,maps}')::int<>1201 then raise exception 'point southwest edge inclusion'; end if;
 if (explore_maps_page(p_point=>'[110,20]')#>>'{total,maps}')::int<>1201 then raise exception 'point northeast edge inclusion'; end if;
 if (explore_maps_page(p_point=>'[110.000001,20]')#>>'{total,maps}')::int<>0 then raise exception 'point immediately outside edge'; end if;
 if (explore_maps_page(p_ids=>jsonb_build_array(md5('1')::uuid))#>>'{total,maps}')::int<>1 then raise exception 'ID restriction'; end if;
 if (explore_maps_page(p_ids=>'[]')#>>'{total,maps}')::int<>0 then raise exception 'empty ID restriction'; end if;
 loop
 result:=explore_maps_page(p_limit=>100,p_cursor=>cursor);
 for row in select value from jsonb_array_elements(result->'maps') loop
  if (row->>'id')::uuid=any(seen) then raise exception 'duplicate cursor tie'; end if;
  seen:=array_append(seen,(row->>'id')::uuid); n:=n+1;
 end loop;
 cursor:=nullif(result->'nextCursor','null'::jsonb);
 exit when cursor is null;
 if n>1300 then raise exception 'cursor never ends'; end if;
 end loop;
 if n<>1202 then raise exception 'cursor dropped rows: %',n; end if;
 result:=explore_maps_page(p_filters=>'{"institution":["Rare institution"]}',p_limit=>1);
 if result->'nextCursor'<>'null'::jsonb then raise exception 'phantom last page'; end if;
 if has_function_privilege('anon','public.explore_maps_page(text,jsonb,jsonb,boolean,integer,jsonb,jsonb,jsonb,boolean)','execute') or has_function_privilege('authenticated','public.explore_maps_page(text,jsonb,jsonb,boolean,integer,jsonb,jsonb,jsonb,boolean)','execute') then raise exception 'public execution allowed'; end if;
end $$;
-- Source supersession requires both halves and respects the request visibility.
insert into maps(id,name,status,is_georeferenced,series_key,allmaps_id,extra_metadata,sheet_half)
values(md5('original')::uuid,'Original','public',true,'halves','scan',null,null),
(md5('west')::uuid,'West','public',true,'halves','scan',jsonb_build_object('mirrors_original_for',md5('original')::uuid::text),'W'),
(md5('east')::uuid,'East','draft',true,'halves','scan',jsonb_build_object('mirrors_original_for',md5('original')::uuid::text),'E');
do $$ begin
 if (explore_maps_page(p_sources=>true,p_filters=>'{"series_key":["halves"]}')#>>'{total,maps}')::int<>2 then raise exception 'partial visible halves hide original'; end if;
 if (explore_maps_page(p_sources=>true,p_staff=>true,p_filters=>'{"series_key":["halves"]}')#>>'{total,maps}')::int<>2 then raise exception 'complete halves do not hide original'; end if;
end $$;
rollback;
