from app.services.component_media_identity import media_key,group_media_inventory
assert media_key('motherboard','ASUS ATX B650 board',1)==media_key('motherboard','ASUS Mini-ITX board',2)
assert media_key('motherboard','ASUS ATX board',1)!=media_key('motherboard','MSI ATX board',2)
for title,key in [('Gigabyte AORUS B650','motherboard_gigabyte'),('ASRock Micro-ATX','motherboard_asrock'),('MSI B850','motherboard_msi')]:
 assert media_key('motherboard',title,1)[1]==key
assert media_key('motherboard','Unknown ATX board',1)[1]=='motherboard_unclassified'
rows=[dict(category='motherboard',title=t,listing_id=i,variant_id=i,variant_ids=[i]) for i,t in enumerate(['ASUS ATX','ASUS Mini-ITX','MSI ATX'],1)]
result=group_media_inventory(rows)
assert len(result)==2 and next(r for r in result if r['title']=='ASUS motherboards')['product_count']==2
print('PASS: manufacturer sharing across form factors; brands remain separate')
